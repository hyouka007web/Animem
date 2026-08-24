package com.tufblade.browser

import android.animation.AnimatorSet
import android.animation.ObjectAnimator
import android.content.Intent
import android.os.Bundle
import android.view.animation.OvershootInterpolator
import androidx.appcompat.app.AppCompatActivity

/**
 * "Anflug"-Animation: Das Logo skaliert von klein/transparent auf volle Größe
 * mit einem leichten Overshoot (wirkt wie ein Herein-Fliegen), danach
 * automatischer Übergang zu MainActivity mit Fade.
 *
 * Bewusst kein Splash-Screen-API-Overkill (Android 12 SplashScreen API) —
 * das würde die Kontrolle über die genaue Animation einschränken. Stattdessen
 * eine simple, volle Kontrolle bietende Activity, sehr kurz (900ms Gesamtdauer),
 * damit der App-Start nicht spürbar verzögert wird.
 */
class SplashActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_splash)

        val logo = findViewById<android.widget.ImageView>(R.id.splashLogo)
        logo.scaleX = 0.6f
        logo.scaleY = 0.6f

        val scaleX = ObjectAnimator.ofFloat(logo, "scaleX", 0.6f, 1.0f)
        val scaleY = ObjectAnimator.ofFloat(logo, "scaleY", 0.6f, 1.0f)
        val alpha = ObjectAnimator.ofFloat(logo, "alpha", 0f, 1f)

        AnimatorSet().apply {
            playTogether(scaleX, scaleY, alpha)
            duration = 550
            interpolator = OvershootInterpolator(1.1f)
            start()
        }

        logo.postDelayed({
            startActivity(Intent(this, MainActivity::class.java))
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out)
            finish()
        }, 900)
    }
}
