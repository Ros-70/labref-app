package com.labref.app

import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * A deliberately narrow instrumented test. The clinical content is already
 * verified by the four-method suite in handover/qa before this ever runs; what
 * is unproven on-device is the *host* — whether the asset loader serves the
 * page, whether localStorage works at the fixed origin, and whether the bridge
 * survives R8.
 *
 * Those three are exactly the things that would ship broken and silent.
 */
@RunWith(AndroidJUnit4::class)
@LargeTest
class SmokeTest {

    private fun evaluate(script: String): String {
        var result = "<none>"
        val latch = CountDownLatch(1)
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            Thread.sleep(3000)   // allow the page to load and scripts to inject
            scenario.onActivity { activity ->
                val webView = activity.findViewById<android.webkit.WebView>(R.id.webview)
                webView.evaluateJavascript(script) { value ->
                    result = value ?: "<null>"
                    latch.countDown()
                }
            }
            latch.await(15, TimeUnit.SECONDS)
        }
        return result
    }

    /**
     * Like evaluate(), but runs a sequence of scripts against the SAME
     * activity/WebView, sleeping between them. Needed for anything that
     * depends on a debounced JS callback (e.g. the 120ms search filter)
     * firing before the next step runs: a single evaluateJavascript call is
     * synchronous, so a debounced effect triggered inside it is never ready
     * by the time that call returns. The sleep happens on the instrumentation
     * thread, not inside onActivity's main-thread block, so it doesn't freeze
     * the WebView's own Looper and starve the timer it's waiting on. Returns
     * the last step's result.
     */
    private fun runSteps(steps: List<Pair<String, Long>>): String {
        var result = "<none>"
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            Thread.sleep(3000)
            for ((script, waitAfterMs) in steps) {
                val latch = CountDownLatch(1)
                scenario.onActivity { activity ->
                    val webView = activity.findViewById<android.webkit.WebView>(R.id.webview)
                    webView.evaluateJavascript(script) { value ->
                        result = value ?: "<null>"
                        latch.countDown()
                    }
                }
                latch.await(15, TimeUnit.SECONDS)
                if (waitAfterMs > 0) Thread.sleep(waitAfterMs)
            }
        }
        return result
    }

    @Test
    fun clinicalContentIsPresentAndComplete() {
        // 180 is the frozen corpus size. If the asset were missing or stale this
        // is the assertion that catches it.
        assertEquals("180", evaluate("LABREF_TESTS.length").trim('"'))
    }

    // build.gradle.kts appends "-debug" to versionName for the debug build
    // type only (versionNameSuffix) -- a cosmetic marker so a debug APK is
    // never mistaken for a release one. This test always runs against
    // connectedDebugAndroidTest, so BuildConfig.VERSION_NAME always carries
    // it; the web asset's own LABREF_VERSION never does and never should
    // (it's build-type-agnostic). Strip it before comparing, or every run
    // of this test fails by construction regardless of whether the content
    // actually matches -- which is exactly what happened the first time
    // this job was ever actually run (Stage 4).
    private fun baseVersion() = BuildConfig.VERSION_NAME.removeSuffix("-debug")

    @Test
    fun versionMatchesTheShippedDataset() {
        // Compared against the APK's own versionName, which build.gradle.kts
        // derives from LABREF_VERSION in the data module. So this asserts the
        // thing that actually matters — that the APK label and the clinical
        // content inside it agree — with no literal to hand-maintain.
        assertEquals(baseVersion(), evaluate("LABREF_VERSION").trim('"'))
    }

    @Test
    fun servedFromTheFixedOriginThatHoldsMyLabData() {
        val origin = evaluate("location.origin").trim('"')
        assertEquals("https://${MainActivity.ASSET_DOMAIN}", origin)
    }

    @Test
    fun localStorageWorks() {
        // My Lab overrides are useless if this fails, and it fails silently
        // under an opaque origin — which is why the origin is pinned.
        val probe = evaluate(
            "(function(){try{localStorage.setItem('__probe','ok');" +
                "var v=localStorage.getItem('__probe');localStorage.removeItem('__probe');" +
                "return v;}catch(e){return 'blocked';}})()"
        ).trim('"')
        assertEquals("ok", probe)
    }

    @Test
    fun nativeBridgeSurvivedShrinking() {
        // Guards the proguard rule. In a release build without it, this is
        // the only test that fails.
        val present = evaluate(
            "(typeof LabRefNative !== 'undefined' && typeof LabRefNative.saveFile === 'function')"
        )
        assertEquals("true", present)
    }

    @Test
    fun printAndDownloadHooksWereInjected() {
        assertEquals("true", evaluate("window.__labrefNativeReady === true"))
    }

    @Test
    fun myLabOverrideRoundTripsThroughStage3Shape() {
        // v2.0 Stage 3 re-keyed My Lab overrides to (test id, rid) --
        // assay:{key:{unit,method,crit}} plus byRid:{rid:{lo,hi}} -- replacing
        // a flat per-component shape with no demographic scope. This is the
        // one thing the desktop QA suite structurally cannot verify: whether
        // that nested shape actually round-trips through THIS WebView's own
        // localStorage/JSON implementation at the fixed asset origin, and
        // whether the UI reads it back correctly on a real reload rather
        // than the in-memory page the first write ran against. Haemoglobin's
        // r1 ("Adult male") is used only because it's a stable, ordinary
        // (non-panel) ref row -- any overridable row would do.
        val writeScript =
            "(function(){" +
                "var o=JSON.parse(localStorage.getItem('labref_v1')||'{}');" +
                "o.local=o.local||{};" +
                "o.local.hb={note:'',assay:{},byRid:{r1:{lo:'13.9',hi:'17.2'}}};" +
                "localStorage.setItem('labref_v1',JSON.stringify(o));" +
                "return 'written';" +
            "})()"
        val reloadScript = "(function(){location.reload();return 'reloading';})()"
        val searchScript =
            "(function(){" +
                "document.querySelector(\"[data-nav='tests']\").click();" +
                "if(!document.getElementById('searchBox').offsetParent){" +
                "  document.getElementById('searchToggle').click();" +
                "}" +
                "var box=document.getElementById('searchBox');" +
                "box.value='Haemoglobin';" +
                "box.dispatchEvent(new Event('input'));" +
                "return 'typed';" +
            "})()"
        val readScript =
            "(function(){" +
                "var row=document.querySelector(\"[data-test='hb']\");" +
                "if(!row) return 'ROW_NOT_FOUND';" +
                "row.click();" +
                "var blk=document.querySelector(\"[data-blk='loc'] .bh\");" +
                "if(!blk) return 'BLOCK_NOT_FOUND';" +
                "blk.click();" +
                "var input=document.querySelector(\".mylab-rid[data-rid='r1'] .lc-lo\");" +
                "return input?input.value:'INPUT_NOT_FOUND';" +
            "})()"

        val value = runSteps(listOf(
            writeScript to 200L,
            reloadScript to 3000L,   // full reinit, same as a fresh app open
            searchScript to 400L,    // clears the 120ms debounce window
            readScript to 0L
        )).trim('"')

        assertEquals(
            "My Lab override written in the Stage 3 shape should read back " +
                "unchanged after a real reload at the fixed origin",
            "13.9", value
        )
    }

    @Test
    fun appRendersItsOwnUi() {
        val hasBar = evaluate("!!document.querySelector('#appbar .title')")
        assertEquals("true", hasBar)
        val version = evaluate("document.querySelector('#appbar .ver').textContent").trim('"')
        assertTrue("app bar should show version ${baseVersion()}, got: $version",
            version.contains(baseVersion()))
    }
}
