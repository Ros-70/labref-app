package com.labref.app

import android.content.Context
import android.os.Bundle
import android.print.PrintAttributes
import android.print.PrintManager
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.webkit.WebSettingsCompat
import androidx.webkit.WebViewAssetLoader
import androidx.webkit.WebViewFeature

/**
 * LabRef — native Android host for the offline single-file clinical reference app.
 *
 * Design rules, each of which has a reason. Read before changing anything here.
 *
 *  1. THE WEB CONTENT IS NEVER MODIFIED. `assets/index.html` is the byte-for-byte
 *     output of `build.py`. Every native capability below is added by injecting
 *     script into the loaded page or by intercepting at the DOM level, so the
 *     frozen app can be rebuilt and dropped in without touching Kotlin.
 *
 *  2. ASSETS ARE SERVED OVER A FIXED HTTPS ORIGIN, not `file://`.
 *     My Lab data (a department's own reference ranges and critical values)
 *     lives in localStorage, which is keyed to origin. If ORIGIN ever changes,
 *     every clinician silently loses their saved values on update. It is a
 *     constant here for that reason. DO NOT CHANGE IT, EVER, including the
 *     "/assets/" path segment and the "index.html" filename.
 *
 *  3. THERE IS NO INTERNET PERMISSION. See AndroidManifest.xml. The asset
 *     loader serves from inside the APK, so nothing is needed. This makes the
 *     offline guarantee an OS-enforced property rather than a promise.
 *
 *  4. ALGORITHMIC DARKENING IS DISABLED. The app ships six themes of its own,
 *     including sepia, pista green and beige. Android 13+ will auto-invert
 *     WebView content in system dark mode and wreck them.
 *
 *  5. WEBVIEW ZOOM IS DISABLED. The app has its own text-size control; two
 *     zoom mechanisms fight each other and break the layout.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var bridge: NativeBridge

    companion object {
        /** See rule 2. Changing any part of this discards users' saved My Lab data. */
        const val ASSET_DOMAIN = "appassets.androidplatform.net"
        const val START_URL = "https://$ASSET_DOMAIN/assets/index.html"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        webView = findViewById(R.id.webview)

        val assetLoader = WebViewAssetLoader.Builder()
            .setDomain(ASSET_DOMAIN)
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true          // localStorage — My Lab depends on it
            // Nothing outside the APK should be reachable.
            allowFileAccess = false
            allowContentAccess = false
            // Rule 5 — the app does its own text sizing.
            setSupportZoom(false)
            builtInZoomControls = false
            displayZoomControls = false
            // The app is already responsive and sized for a phone viewport.
            useWideViewPort = false
            loadWithOverviewMode = false
            cacheMode = WebSettings.LOAD_NO_CACHE
        }

        // Rule 4 — never let the system invert the app's own themes.
        if (WebViewFeature.isFeatureSupported(WebViewFeature.ALGORITHMIC_DARKENING)) {
            WebSettingsCompat.setAlgorithmicDarkeningAllowed(webView.settings, false)
        }

        bridge = NativeBridge(this, webView)
        webView.addJavascriptInterface(bridge, NativeBridge.NAME)
        webView.webChromeClient = bridge.chromeClient()

        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView, request: WebResourceRequest
            ): WebResourceResponse? = assetLoader.shouldInterceptRequest(request.url)

            /**
             * The app is entirely self-contained, so any navigation away from our
             * own origin is either a bug or something injected. Refuse all of it
             * rather than failing obscurely with no INTERNET permission.
             */
            override fun shouldOverrideUrlLoading(
                view: WebView, request: WebResourceRequest
            ): Boolean = request.url.host != ASSET_DOMAIN

            override fun onPageFinished(view: WebView, url: String) {
                injectNativeHooks(view)
            }
        }

        if (savedInstanceState == null) {
            webView.loadUrl(START_URL)
        } else {
            webView.restoreState(savedInstanceState)
        }

        installBackHandler()
    }

    /**
     * Everything the web app needs from the platform, added without editing it.
     *
     * `window.print()` — the handout's Print button calls it; WebView ignores it
     * entirely, so it is redirected to Android's PrintManager.
     *
     * Blob downloads — My Lab profile export and full backup build a Blob, attach
     * it to an <a download>, and click it. WebView's DownloadListener cannot fetch
     * a blob: URL, so instead a capture-phase listener catches the click before
     * the default action, reads the blob as text, and hands it to the bridge to
     * write through the system file picker. Capture phase matters: the object URL
     * is revoked 500 ms after the click, so this must not be deferred.
     */
    private fun injectNativeHooks(view: WebView) {
        view.evaluateJavascript(
            """
            (function () {
              if (window.__labrefNativeReady) return;
              window.__labrefNativeReady = true;

              window.print = function () { ${NativeBridge.NAME}.printPage(); };

              document.addEventListener('click', function (e) {
                var a = e.target && e.target.closest && e.target.closest('a[download]');
                if (!a) return;
                var href = a.getAttribute('href') || '';
                if (href.lastIndexOf('blob:', 0) !== 0) return;
                e.preventDefault();
                e.stopImmediatePropagation();
                var name = a.getAttribute('download') || 'labref-export.json';
                fetch(href)
                  .then(function (r) { return r.text(); })
                  .then(function (t) { ${NativeBridge.NAME}.saveFile(name, t); })
                  .catch(function (err) { ${NativeBridge.NAME}.reportError(String(err)); });
              }, true);
            })();
            """.trimIndent(), null
        )
    }

    /**
     * The web app keeps its own navigation stack and shows or hides its in-app
     * back button accordingly; it does not push browser history entries, so
     * WebView.canGoBack() is always false. Hardware and gesture back therefore
     * ask the page whether it has somewhere to go, and only exit if it does not.
     * This reads the page's existing #backBtn rather than requiring a hook in it.
     */
    private fun installBackHandler() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                webView.evaluateJavascript(
                    """
                    (function () {
                      var b = document.getElementById('backBtn');
                      if (b && b.style.display !== 'none') { b.click(); return 'handled'; }
                      return 'exit';
                    })();
                    """.trimIndent()
                ) { result ->
                    if (result == null || result.contains("exit")) {
                        isEnabled = false
                        onBackPressedDispatcher.onBackPressed()
                    }
                }
            }
        })
    }

    fun printCurrentPage() {
        val adapter = webView.createPrintDocumentAdapter(getString(R.string.print_job_name))
        val manager = getSystemService(Context.PRINT_SERVICE) as PrintManager
        manager.print(
            getString(R.string.print_job_name),
            adapter,
            PrintAttributes.Builder().build()
        )
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        webView.saveState(outState)
    }
}
