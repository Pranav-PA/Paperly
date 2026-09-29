package com.paperly.app

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.paperly.app.ui.chat.ChatScreen
import com.paperly.app.ui.chat.ChatViewModel
import com.paperly.app.ui.home.HomeScreen
import com.paperly.app.ui.home.HomeViewModel
import com.paperly.app.ui.login.LoginScreen
import com.paperly.app.ui.login.LoginViewModel
import com.paperly.app.ui.paper.PaperScreen
import com.paperly.app.ui.paper.PaperViewModel
import com.paperly.app.ui.theme.PaperlyTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val app = application as PaperlyApp

        setContent {
            PaperlyTheme {
                val session by app.sessionStore.session.collectAsStateWithLifecycle()
                AnimatedContent(targetState = session.isLoggedIn, transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "auth") { loggedIn ->
                    if (loggedIn) {
                        MainNavigation(app)
                    } else {
                        LoginScreen(paperlyViewModel(key = "login") { LoginViewModel(app.repository, app.sessionStore) })
                    }
                }
            }
        }
    }
}

@Composable
inline fun <reified VM : ViewModel> paperlyViewModel(key: String, crossinline create: () -> VM): VM =
    viewModel(key = key, factory = viewModelFactory { initializer { create() } })

@Composable
private fun MainNavigation(app: PaperlyApp) {
    val nav = rememberNavController()
    NavHost(
        navController = nav,
        startDestination = "home",
        enterTransition = { slideInHorizontally { it / 4 } + fadeIn() },
        exitTransition = { fadeOut() },
        popEnterTransition = { fadeIn() },
        popExitTransition = { slideOutHorizontally { it / 4 } + fadeOut() }
    ) {
        composable("home") {
            HomeScreen(
                vm = paperlyViewModel("home") { HomeViewModel(app.repository, app.sessionStore) },
                onOpenConversation = { id, prompt ->
                    nav.navigate("chat/$id" + (prompt?.let { "?prompt=${Uri.encode(it)}" } ?: ""))
                },
                onOpenPaper = { id, _ -> nav.navigate("paper/$id") }
            )
        }
        composable(
            "chat/{id}?prompt={prompt}",
            arguments = listOf(
                navArgument("id") { type = NavType.StringType },
                navArgument("prompt") { type = NavType.StringType; nullable = true; defaultValue = null }
            )
        ) { entry ->
            val id = entry.arguments?.getString("id").orEmpty()
            val prompt = entry.arguments?.getString("prompt")
            ChatScreen(
                vm = paperlyViewModel("chat-$id") { ChatViewModel(app.repository, id, prompt) },
                onBack = { nav.popBackStack() },
                onOpenPaper = { paperId, _ -> nav.navigate("paper/$paperId") }
            )
        }
        composable("paper/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType })) { entry ->
            val id = entry.arguments?.getString("id").orEmpty()
            PaperScreen(
                vm = paperlyViewModel("paper-$id") { PaperViewModel(app.repository, id) },
                onBack = { nav.popBackStack() }
            )
        }
    }
}
