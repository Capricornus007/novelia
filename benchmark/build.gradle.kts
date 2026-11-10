plugins {
    id("com.android.test")
    id("androidx.baselineprofile")
}

android {
    namespace = "cc.novelia.benchmark"
    compileSdk = 37
    defaultConfig {
        minSdk = 28
        targetSdk = 37
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    targetProjectPath = ":app"
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
}

baselineProfile { useConnectedDevices = true }
dependencies {
    implementation("androidx.test.ext:junit:1.4.0-alpha03")
    implementation("androidx.test:runner:1.8.0-alpha03")
    implementation("androidx.test.uiautomator:uiautomator:2.4.1")
    implementation("androidx.benchmark:benchmark-macro-junit4:1.6.0-alpha01")
}
