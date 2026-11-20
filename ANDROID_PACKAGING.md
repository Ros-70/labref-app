# Android Packaging — decision and scaffold

**Decision: native Android with a WebView host. The scaffold is in
`android/` and is ready to build.**

This reverses the Capacitor recommendation made at the v1.1 freeze. The reason
is a constraint that did not exist then: **the app will be built by Claude Code
autonomously, through a connected GitHub repository, without a human watching
the build.** That changes which trade-offs matter.

---

## 1. Why not Capacitor

Capacitor was a reasonable call for a human-driven build. It is the wrong call
for an unattended one.

**The benefit does not apply here.** Capacitor exists so that one web codebase
can target iOS, Android and the web. LabRef is Android-only, a single file, with
no server and no web deployment. You pay the entire abstraction cost and collect
almost none of the benefit.

**Its failure modes are the kind an autonomous agent handles worst.** The
characteristic Capacitor failure is `npx cap sync` breaking on a version
mismatch somewhere in the Capacitor ↔ Android Gradle Plugin ↔ Gradle ↔ Kotlin ↔
JDK chain. When that happens:

- the root cause is not in the repository,
- it is not in the error message,
- fixing it requires knowing a compatibility matrix that is not written down
  anywhere in the project,
- and the error surfaces inside generated code that nobody wrote and that the
  agent cannot reason about from the repo alone.

A native build's characteristic failure is a compile error in a file the agent
itself wrote, with a file name and a line number. That difference decides it.

**It doubles the dependency surface.** Capacitor means two package ecosystems
(npm and Gradle) that must stay mutually compatible. Native means one.

**It makes diffs less reviewable.** With a generated `android/` project, much of
what is in the repo is machine output, and `git diff` stops being a reliable
account of what changed. When you are auditing autonomous work rather than
watching it happen, a meaningful diff is a primary safety mechanism.

**Reconsider Capacitor only if** the project later wants iOS as well, or wants
to ship LabRef as a hosted website in parallel. At that point it becomes the
right tool for a genuinely different reason.

(Trusted Web Activity was also reconsidered and remains wrong here, for the
reason given at v1.1: it requires hosting the app at a verified domain, and this
project has deliberately avoided standing up any infrastructure.)

---

## 2. What native cost us, concretely

The capabilities that originally justified Capacitor come to roughly 200 lines
of standard Kotlin, all of it written and in `android/`:

| Capability | Where | Approx. |
|---|---|---|
| My Lab export / backup via the system file picker | `NativeBridge.saveFile` | 35 lines |
| My Lab import / restore via the system picker | `NativeBridge.chromeClient` | 25 lines |
| Printing the patient-prep handout | `MainActivity.printCurrentPage` | 12 lines |
| Share sheet (available, not yet used by the app) | `NativeBridge.shareText` | 12 lines |

Printing would have needed hand-written native code under Capacitor too, so the
real saving Capacitor offered was smaller than it looked.

A biometric/PIN lock, if ever wanted, is about 40 more lines with
`androidx.biometric` and needs no packaging change.

---

## 3. What native bought us

**The offline guarantee becomes OS-enforced.** `AndroidManifest.xml` has **no
`INTERNET` permission**. Content is served from inside the APK by
`WebViewAssetLoader`, so none is needed. "Works fully offline" stops being a
promise in a README and becomes a property Android enforces, visible on the Play
listing, which no later code change can quietly break.

**One toolchain, fully pinned.** Every version lives in
`android/gradle/libs.versions.toml`, pinned — no version ranges anywhere. A
build that passes today passes next month. For unattended builds that matters
more than staying current.

**The whole system is in the repo.** Nineteen files, all hand-written, nothing
generated. An agent can read all of it.

---

## 4. The decision that protects users' data — read this one

**`MainActivity.ASSET_DOMAIN` and `START_URL` must never change.**

My Lab stores a department's own reference ranges and critical values in
`localStorage`, which the browser keys to **origin**. The app is served over a
fixed origin:

```
https://appassets.androidplatform.net/assets/index.html
```

If any part of that changes — the domain, the `/assets/` path segment, or the
`index.html` filename — every clinician silently loses every locally saved
reference range on update. The app will look like it is working perfectly.

This is why:

- the asset is renamed to the fixed `index.html` by the Gradle staging task,
  rather than carrying the version number in its filename;
- `file://` was rejected in favour of `WebViewAssetLoader`, since `file://`
  origins are opaque and localStorage behaviour under them is unreliable;
- there is an instrumented test (`SmokeTest.servedFromTheFixedOriginThatHoldsMyLabData`)
  whose only job is to fail if someone changes it.

---

## 5. Two other things that would ship broken and silent

**Algorithmic darkening is explicitly disabled.** On Android 13 and later, the
system will automatically invert WebView content when the device is in dark
mode. LabRef ships six themes of its own, and sepia, pista green and beige would
all be wrecked by it. `WebSettingsCompat.setAlgorithmicDarkeningAllowed(…,
false)` in `MainActivity` prevents it. A debug build on a light-mode device will
never reveal this.

**The JavaScript bridge is kept by a ProGuard rule.** R8 would otherwise rename
or remove `NativeBridge`, because nothing in Kotlin calls it — it is reached by
name from injected script. The release build would install fine and then fail
the moment a clinician taps Export or Print. `app/proguard-rules.pro` keeps it,
and `SmokeTest.nativeBridgeSurvivedShrinking` is the test that catches it if the
rule is ever dropped.

`allowBackup` is set to **false**, deliberately. Left at the default, Android
would copy locally saved reference ranges to the user's Google account. That may
well be acceptable, but it should be a hospital's decision rather than an
inherited framework default. `backup_rules.xml` is already written and correctly
scoped if you switch it on.

---

## 6. The frozen app is not modified — at all

Every native capability is added by **injecting script into the loaded page** or
by **intercepting at the DOM level**. `shell.html` and
`labref_data_v1.10.js` are untouched, and `assets/index.html` is the
byte-for-byte output of `build.py`.

This was a design goal, not a coincidence: it means the clinical content can be
rebuilt and dropped in at any time without a Kotlin change, and the native host
can be changed without re-verifying the clinical data.

Three integration points were read out of the frozen shell rather than assumed:

| Need | What the shell actually does | How the host handles it |
|---|---|---|
| Hardware/gesture back | Keeps its own `navStack`; shows `#backBtn` with `style.display`; pushes no history entries, so `canGoBack()` is always `false` | Back asks the page whether `#backBtn` is visible, clicks it if so, exits only if not |
| Export / backup | Builds a `Blob`, attaches it to `<a download>`, clicks it, revokes the object URL after 500 ms | A **capture-phase** click listener catches `a[download]` with a `blob:` href, reads it synchronously, passes it to `saveFile`. Capture phase matters — deferring past the 500 ms revoke would lose the data |
| Print handout | Calls `window.print()`, which WebView ignores entirely | `window.print` is replaced by injection and routed to `PrintManager` |

---

## 7. How to build it

```bash
# 1. Build the clinical content (required — Gradle fails without it)
cd handover/app && python3 -I build.py

# 2. Build the app
cd ../android && ./gradlew assembleDebug
```

The Gradle `stageClinicalAsset` task copies the built HTML into assets and is
wired into `preBuild`, so there is no separate step to forget. It **fails the
build** rather than warning if the HTML is missing, because an APK with no
clinical content would install and launch to a blank screen — worse than not
building at all.

The built HTML is deliberately **not committed**. The single source of truth for
clinical content is `labref_data_v1.10.js`; a committed build artifact would
eventually drift from it.

`gradlew` and the wrapper JAR are not in this package — run
`gradle wrapper --gradle-version 8.9` once, or let the CI action provide Gradle.

---

## 8. CI — and why the order matters

`.github/workflows/build.yml` runs four jobs:

1. **`clinical-qa`** — all four verification methods against the built HTML.
   **A hard gate.** No Android toolchain involved, so it fails fast and cheap.
2. **`android-build`** — needs `clinical-qa`. Debug APK, lint, unit tests.
3. **`instrumented-smoke`** — needs `android-build`. Runs on an emulator and
   proves the three things that fail silently: the asset loader serves the page,
   localStorage works at the pinned origin, the bridge survived R8. Emulators
   are slow and occasionally flaky on hosted runners, so this runs on pull
   requests and on demand rather than on every push.
4. **`release-bundle`** — manual only. Signing comes from repository secrets;
   without them it produces an unsigned bundle rather than failing, so the build
   stays verifiable by anyone without key access.

**Clinical QA runs before anything is packaged, and blocks it.** For a clinical
reference app that ordering matters more than build speed: a data error must not
be able to reach an installable artifact.

---

## 9. Before the first release — verify these

These are the items that depend on things outside this package, or on Play
policy that moves:

- **`targetSdk` / `compileSdk` are 35.** Play raises its minimum target API
  roughly once a year. Check the current requirement and bump both together —
  it is a one-line change each in `app/build.gradle.kts`.
- **`applicationId` is `com.labref.app`.** Change it if the organisation has its
  own namespace, and do it *before* the first Play upload — it cannot be changed
  afterwards. (Note: a package name cannot begin with `in.`, as that is a Kotlin
  keyword.)
- **Launcher icons.** `icons/android/` holds the rendered `mipmap-*` assets and
  the adaptive foreground/background layers; copy them into
  `android/app/src/main/res/`. The scaffold references `@mipmap/ic_launcher`
  and will not build until they are in place.
- **Signing keystore.** Generate it, store it somewhere durable — losing it
  means never being able to update the app — and add the four
  `ANDROID_*` repository secrets.
- **Play Data Safety declaration.** The honest answer is that no data is
  collected or transmitted: there is no network permission, no analytics, no
  crash reporter, and My Lab values never leave the device. Say exactly that.
- **Medical disclaimer.** The listing and the app's About screen should state
  that LabRef is a reference aid for clinicians, that values are
  method-dependent, and that the laboratory's own ranges take precedence. The
  app already carries the My Lab feature for exactly this reason; the listing
  should not overstate what the shipped ranges are.
