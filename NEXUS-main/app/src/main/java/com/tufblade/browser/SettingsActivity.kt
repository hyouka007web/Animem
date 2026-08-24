package com.tufblade.browser

import android.os.Bundle
import android.widget.RadioGroup
import android.widget.Switch
import androidx.appcompat.app.AppCompatActivity

class SettingsActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        findViewById<android.widget.ImageButton>(R.id.settingsBackButton).setOnClickListener { finish() }

        val group = findViewById<RadioGroup>(R.id.searchEngineGroup)
        val currentEngine = NexusSettings.getSearchEngine(this)
        val checkedId = when (currentEngine) {
            NexusSettings.SearchEngine.DUCKDUCKGO -> R.id.engineDuckDuckGo
            NexusSettings.SearchEngine.GOOGLE -> R.id.engineGoogle
            NexusSettings.SearchEngine.BING -> R.id.engineBing
        }
        group.check(checkedId)

        group.setOnCheckedChangeListener { _, checkedButtonId ->
            val engine = when (checkedButtonId) {
                R.id.engineGoogle -> NexusSettings.SearchEngine.GOOGLE
                R.id.engineBing -> NexusSettings.SearchEngine.BING
                else -> NexusSettings.SearchEngine.DUCKDUCKGO
            }
            NexusSettings.setSearchEngine(this, engine)
        }

        val adBlockSwitch = findViewById<Switch>(R.id.adBlockSwitch)
        adBlockSwitch.isChecked = NexusSettings.isAdBlockEnabled(this)
        adBlockSwitch.setOnCheckedChangeListener { _, isChecked ->
            NexusSettings.setAdBlockEnabled(this, isChecked)
        }
    }
}
