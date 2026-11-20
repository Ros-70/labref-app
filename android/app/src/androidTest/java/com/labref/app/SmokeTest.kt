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

    @Test
    fun clinicalContentIsPresentAndComplete() {
        // 180 is the frozen corpus size. If the asset were missing or stale this
        // is the assertion that catches it.
        assertEquals("180", evaluate("LABREF_TESTS.length").trim('"'))
    }

    @Test
    fun versionMatchesTheShippedDataset() {
        assertEquals("1.10", evaluate("LABREF_VERSION").trim('"'))
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
    fun appRendersItsOwnUi() {
        val hasBar = evaluate("!!document.querySelector('#appbar .title')")
        assertEquals("true", hasBar)
        val version = evaluate("document.querySelector('#appbar .ver').textContent").trim('"')
        assertTrue("app bar should show the version, got: $version", version.contains("1.10"))
    }
}
