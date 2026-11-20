# LabRef — native Android host

The whole app is a WebView serving one offline HTML file from inside the APK.
There is no network code, no analytics, no dependency injection and no
Compose. Nineteen files, all hand-written.

Read `../ANDROID_PACKAGING.md` for *why* it is built this way. This file is
how to work on it.

## Build

```bash
cd ../app && python3 -I build.py      # produces LabRef_v1.10.html — required
cd ../android && ./gradlew assembleDebug
```

Gradle copies the HTML into `app/src/main/assets/index.html` automatically
(`stageClinicalAsset`, wired into `preBuild`) and **fails** if it is absent.
The HTML is not committed: the source of truth is `../app/labref_data_v1.10.js`.

`gradlew` and the wrapper JAR are not included — run
`gradle wrapper --gradle-version 8.9` once.

## Layout

```
gradle/libs.versions.toml     every version, pinned — change versions only here
settings.gradle.kts           repositories; FAIL_ON_PROJECT_REPOS
app/build.gradle.kts          SDK levels, signing, the asset staging task
app/proguard-rules.pro        keeps NativeBridge alive through R8
app/src/main/AndroidManifest.xml
app/src/main/java/com/labref/app/
    MainActivity.kt           WebView setup, asset loader, back handling, script injection
    NativeBridge.kt           the only JS-facing surface: save, print, file picker, share
    LabRefApplication.kt      empty by design
app/src/main/res/             layout, theme, strings, backup rules
app/src/androidTest/.../SmokeTest.kt   on-device checks
```

## Four things not to change without reading first

1. **`MainActivity.ASSET_DOMAIN` / `START_URL`.** Users' saved My Lab reference
   ranges live in `localStorage`, keyed to origin. Changing the domain, the
   `/assets/` path or the `index.html` filename silently wipes them on update.
   `SmokeTest.servedFromTheFixedOriginThatHoldsMyLabData` exists to stop this.
2. **The absent `INTERNET` permission.** Its absence is the offline guarantee.
   If something seems to need it, that is a design question to raise, not a
   line to add.
3. **`setAlgorithmicDarkeningAllowed(false)`.** Without it, Android 13+ inverts
   the WebView in dark mode and destroys the app's sepia, pista and beige
   themes. A light-mode debug build will never show you this.
4. **The ProGuard keep rule for `NativeBridge`.** Nothing in Kotlin calls it —
   it is reached by name from injected script, so R8 will remove it. The
   release build then installs fine and breaks the first time someone taps
   Export or Print.

## Tests

```bash
./gradlew testDebugUnitTest          # none yet — the host has little pure logic
./gradlew connectedDebugAndroidTest  # SmokeTest, needs a device or emulator
```

`SmokeTest` is deliberately narrow. The clinical content is already verified by
the four-method suite in `../qa` before this ever runs; what is unproven
on-device is the host — whether assets are served, whether localStorage
persists at the pinned origin, and whether the bridge survived shrinking. Those
are the three failures that would ship silently.

Verify a **release** build on a device at least once before each Play upload.
Debug builds skip R8, so they cannot catch the bridge-stripping failure.

## Adding a native capability

The frozen web app is never edited. Add a `@JavascriptInterface` method to
`NativeBridge`, then call it from the injected script in
`MainActivity.injectNativeHooks` — either directly, or by overriding a web API
the page already uses (which is how `window.print` is handled). Add a
corresponding assertion to `SmokeTest` and a keep rule if R8 could reach it.
