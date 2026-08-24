package com.tufblade.browser.tabs

import org.mozilla.geckoview.GeckoSession

data class Tab(
    val session: GeckoSession,
    var title: String = "Neuer Tab",
    var url: String = ""
)

/** Einfache In-Memory-Tab-Verwaltung. Kein Persistieren über App-Neustarts hinweg (TODO). */
class TabManager {
    private val _tabs = mutableListOf<Tab>()
    val tabs: List<Tab> get() = _tabs

    var activeIndex: Int = -1
        private set

    fun addTab(tab: Tab): Int {
        _tabs.add(tab)
        activeIndex = _tabs.size - 1
        return activeIndex
    }

    fun setActive(index: Int) {
        if (index in _tabs.indices) activeIndex = index
    }

    fun activeTab(): Tab? = _tabs.getOrNull(activeIndex)

    fun closeTab(index: Int) {
        if (index !in _tabs.indices) return
        _tabs[index].session.close()
        _tabs.removeAt(index)
        activeIndex = when {
            _tabs.isEmpty() -> -1
            activeIndex >= _tabs.size -> _tabs.size - 1
            else -> activeIndex
        }
    }

    fun closeAll() {
        _tabs.forEach { it.session.close() }
        _tabs.clear()
        activeIndex = -1
    }
}
