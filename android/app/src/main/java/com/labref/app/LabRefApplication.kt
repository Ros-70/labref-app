package com.labref.app

import android.app.Application

/**
 * Nothing to initialise — there is no analytics, no crash reporter, no network
 * client and no dependency-injection graph. The class exists so that if any of
 * those is ever added there is an obvious place for it, and so the manifest's
 * android:name does not need to change later.
 */
class LabRefApplication : Application()
