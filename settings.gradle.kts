pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // GeckoView nightly/release channel — swap to the release channel URL you target
        maven(url = "https://maven.mozilla.org/maven2/")
    }
}

rootProject.name = "TUF-Blade Browser"
include(":app")
