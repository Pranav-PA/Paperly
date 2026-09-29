package com.paperly.app.ui.navigation

sealed class Screen(val route: String) {
    object Login : Screen("login")
    object Home : Screen("home")
    object Chat : Screen("chat/{conversationId}") {
        fun createRoute(conversationId: String) = "chat/$conversationId"
    }
    object Progress : Screen("progress/{conversationId}") {
        fun createRoute(conversationId: String) = "progress/$conversationId"
    }
    object Editor : Screen("editor/{paperId}") {
        fun createRoute(paperId: String) = "editor/$paperId"
    }
    object Export : Screen("export/{paperId}") {
        fun createRoute(paperId: String) = "export/$paperId"
    }
    object History : Screen("history")
}
