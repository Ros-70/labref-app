plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

/**
 * Reads LABREF_VERSION out of the clinical data module so the APK's versionName
 * is derived from the dataset instead of hand-copied beside it.
 *
 * The data file is located by glob, not by a hardcoded version, for the same
 * reason the build and QA scripts are: a version baked into a path is a path
 * that goes stale silently. Anything unexpected here fails configuration loudly
 * rather than shipping an APK labelled with the wrong dataset version.
 */
fun clinicalDataVersion(): String {
    val appDir = rootProject.file("../app")
    val hits = (appDir.listFiles()?.filter {
        it.name.startsWith("labref_data_v") && it.name.endsWith(".js")
    } ?: emptyList()).sortedBy { it.name }

    if (hits.isEmpty())
        throw GradleException("No labref_data_v*.js found in ${appDir.absolutePath} — " +
            "cannot determine the clinical data version this APK would ship.")
    if (hits.size > 1)
        throw GradleException("${hits.size} data modules found (${hits.joinToString { it.name }}) — " +
            "remove stale versions so the APK cannot be labelled with the wrong one.")

    val m = Regex("""LABREF_VERSION\s*=\s*"([^"]+)"""").find(hits[0].readText())
        ?: throw GradleException("Could not read LABREF_VERSION from ${hits[0].name}.")
    return m.groupValues[1]
}

/**
 * Locates the built single-file app, again by glob rather than a baked-in
 * version. When it has not been built yet, this returns the path it OUGHT to
 * live at (derived from the data module's version) so the staging task can fail
 * with an accurate message instead of a misleading one.
 */
fun clinicalHtmlFile(): File {
    val appDir = rootProject.file("../app")
    val hits = (appDir.listFiles()?.filter {
        it.name.startsWith("LabRef_v") && it.name.endsWith(".html")
    } ?: emptyList()).sortedBy { it.name }

    if (hits.size > 1)
        throw GradleException("${hits.size} built apps found (${hits.joinToString { it.name }}) — " +
            "remove stale builds so the APK cannot ship the wrong dataset.")

    return hits.firstOrNull() ?: File(appDir, "LabRef_v${clinicalDataVersion()}.html")
}

android {
    namespace = "com.labref.app"

    // ---------------------------------------------------------------------
    // Play Store raises its minimum target API roughly once a year. Verify
    // the current requirement before a release; bumping is a one-line change
    // here and in compileSdk, and they must move together.
    // ---------------------------------------------------------------------
    compileSdk = 35

    defaultConfig {
        applicationId = "com.labref.app"
        minSdk = 24          // Android 7.0 — covers the older hospital devices
                             // still in service, and every one of them has a
                             // modern updatable WebView via Play Services.
        targetSdk = 35

        // versionName is READ OUT of the clinical data module rather than typed
        // here, so the APK can always be traced to the exact dataset it shipped
        // and the two cannot drift. A hand-maintained copy drifted silently once
        // already (the QA suite verifying a stale build), so it is derived now.
        // versionCode stays manual: Play requires it to increase monotonically,
        // which no version string can express reliably.
        versionCode = 200
        versionName = clinicalDataVersion()

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // No locale splitting: the app is English and self-contained.
        resourceConfigurations += listOf("en")
    }

    // Signing material never lives in the repository. CI supplies it through
    // secrets as environment variables; if they are absent the release build
    // still succeeds and produces an unsigned bundle, so the build stays
    // verifiable by anyone without access to the key.
    val keystorePath = System.getenv("LABREF_KEYSTORE")
    val hasSigningConfig = !keystorePath.isNullOrBlank() && file(keystorePath).exists()

    signingConfigs {
        if (hasSigningConfig) {
            create("release") {
                storeFile = file(keystorePath!!)
                storePassword = System.getenv("LABREF_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("LABREF_KEY_ALIAS")
                keyPassword = System.getenv("LABREF_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            // R8 is on, but only the Kotlin host is shrinkable — the clinical
            // content is an asset and is never touched by it.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            if (hasSigningConfig) {
                signingConfig = signingConfigs.getByName("release")
            } else {
                logger.lifecycle(
                    "LabRef: no signing keystore in the environment — " +
                        "the release build will be unsigned."
                )
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        // No Compose, no view binding, no BuildConfig fields needed. Every
        // feature left off is one less thing in the dependency graph that can
        // break an unattended build.
        buildConfig = false
    }

    packaging {
        resources.excludes += setOf(
            "META-INF/AL2.0", "META-INF/LGPL2.1", "/META-INF/{AL2.0,LGPL2.1}"
        )
    }

    lint {
        // Fail the build on a real error, but do not let a style warning stop
        // an autonomous release.
        abortOnError = true
        warningsAsErrors = false
        checkReleaseBuilds = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.constraintlayout)
    implementation(libs.androidx.activity.ktx)   // registerForActivityResult, OnBackPressedCallback
    implementation(libs.androidx.webkit)         // WebViewAssetLoader, algorithmic darkening

    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.test.runner)   // AndroidJUnitRunner + test filters
}

// ---------------------------------------------------------------------------
// Copies the built clinical app into assets, so a build can never silently
// ship a stale dataset. Wired into preBuild, so `./gradlew assembleDebug`
// alone is enough — there is no separate step to forget.
//
// It deliberately FAILS rather than warning if the HTML is missing: an APK
// containing no clinical content would install and launch to a blank screen,
// which is worse than not building.
// ---------------------------------------------------------------------------
val stageClinicalAsset by tasks.registering {
    val source = clinicalHtmlFile()
    val destDir = layout.projectDirectory.dir("src/main/assets")

    // Declared so Gradle's up-to-date checking works, without making the task
    // a Copy: a Copy task with a missing source is skipped as NO-SOURCE and its
    // doFirst never runs, which would defeat the guard below entirely.
    inputs.file(source).optional(true)
    outputs.file(destDir.file("index.html"))

    doLast {
        if (!source.exists()) {
            throw GradleException(
                """
                Clinical content not found at:
                  ${source.absolutePath}

                Build it first:
                  cd app && python3 -I build.py

                The HTML is not committed to the repository on purpose — the
                single source of truth is app/labref_data_v*.js, and a committed
                build artifact would eventually drift from it.
                """.trimIndent()
            )
        }
        copy {
            from(source)
            into(destDir)
            // Fixed filename. MainActivity.START_URL depends on it, and so
            // therefore does the localStorage origin that holds every user's
            // My Lab values. See ANDROID_PACKAGING.md section 4.
            rename { "index.html" }
        }
        logger.lifecycle("LabRef: staged clinical content (${source.length() / 1024} KB)")
    }
}

tasks.named("preBuild") {
    dependsOn(stageClinicalAsset)
}
