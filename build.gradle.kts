// TUF-Blade Browser — root build file
plugins {
    id("com.android.application") version "9.3.1" apply false
    id("com.chaquo.python") version "16.0.0" apply false
}

tasks.register("clean", Delete::class) {
    delete(rootProject.buildDir)
}
