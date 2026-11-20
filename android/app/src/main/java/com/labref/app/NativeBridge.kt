package com.labref.app

import android.content.Intent
import android.net.Uri
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebView
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity

/**
 * The only surface exposed to the web app, and deliberately a small one.
 *
 * Three capabilities, each one something the frozen HTML already tries to do and
 * that a plain WebView cannot:
 *
 *   saveFile()    — My Lab profile export and full backup (Blob downloads)
 *   printPage()   — the printable patient-prep handout
 *   file chooser  — My Lab profile import and backup restore (<input type="file">)
 *
 * Note on exposure: addJavascriptInterface grants the page access to these
 * methods. That is safe here only because the page is served from inside the APK
 * over a fixed origin and navigation off that origin is blocked
 * (MainActivity.shouldOverrideUrlLoading). If either of those protections is
 * ever relaxed, this class becomes an attack surface — reconsider it then.
 */
class NativeBridge(
    private val activity: AppCompatActivity,
    private val webView: WebView
) {
    companion object {
        /** The JS global the page sees. Referenced in MainActivity's injected script. */
        const val NAME = "LabRefNative"
        private const val TAG = "LabRefNative"
    }

    /** Content pending a destination, held between the picker request and its result. */
    private var pendingContent: String? = null

    private var fileChooserCallback: ValueCallback<Array<Uri>>? = null

    private val createDocument: ActivityResultLauncher<String> =
        activity.registerForActivityResult(
            ActivityResultContracts.CreateDocument("application/json")
        ) { uri: Uri? ->
            val body = pendingContent
            pendingContent = null
            if (uri == null || body == null) return@registerForActivityResult
            try {
                activity.contentResolver.openOutputStream(uri)?.use { out ->
                    out.write(body.toByteArray(Charsets.UTF_8))
                }
            } catch (e: Exception) {
                Log.e(TAG, "could not write export", e)
            }
        }

    private val openDocument: ActivityResultLauncher<Array<String>> =
        activity.registerForActivityResult(
            ActivityResultContracts.OpenDocument()
        ) { uri: Uri? ->
            // The web app's <input type="file"> handler reads the file itself with
            // FileReader, so handing back the URI is all that is required.
            fileChooserCallback?.onReceiveValue(if (uri == null) emptyArray() else arrayOf(uri))
            fileChooserCallback = null
        }

    /**
     * Hands exported JSON to the system file picker so the clinician chooses where
     * it goes, instead of it landing silently in Downloads.
     */
    @JavascriptInterface
    fun saveFile(suggestedName: String, content: String) {
        pendingContent = content
        activity.runOnUiThread {
            createDocument.launch(suggestedName.ifBlank { "labref-export.json" })
        }
    }

    @JavascriptInterface
    fun printPage() {
        activity.runOnUiThread { (activity as MainActivity).printCurrentPage() }
    }

    /** Lets a failed blob read surface in logcat rather than vanishing. */
    @JavascriptInterface
    fun reportError(message: String) {
        Log.w(TAG, "web reported: $message")
    }

    fun chromeClient(): WebChromeClient = object : WebChromeClient() {
        override fun onShowFileChooser(
            view: WebView,
            callback: ValueCallback<Array<Uri>>,
            params: FileChooserParams
        ): Boolean {
            fileChooserCallback?.onReceiveValue(null)   // abandon any earlier request
            fileChooserCallback = callback
            return try {
                openDocument.launch(arrayOf("application/json", "text/plain", "*/*"))
                true
            } catch (e: Exception) {
                Log.e(TAG, "no activity available to pick a file", e)
                fileChooserCallback = null
                false
            }
        }
    }

    /** Available if a share action is ever wanted; nothing in the app calls it yet. */
    @JavascriptInterface
    fun shareText(subject: String, body: String) {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, subject)
            putExtra(Intent.EXTRA_TEXT, body)
        }
        activity.runOnUiThread {
            activity.startActivity(Intent.createChooser(intent, subject))
        }
    }
}
