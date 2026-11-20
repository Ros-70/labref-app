# The JavaScript bridge is called by name from injected script, so R8 must not
# rename or remove it. Without this the release build installs fine and then
# fails at runtime the moment a clinician taps Export or Print — a failure that
# a debug build will never reproduce.
-keepclassmembers class com.labref.app.NativeBridge {
    @android.webkit.JavascriptInterface <methods>;
}
-keep class com.labref.app.NativeBridge { *; }

# WebView's own callback plumbing.
-keepclassmembers class * extends android.webkit.WebChromeClient {
    public void *(android.webkit.WebView, java.lang.String);
}
