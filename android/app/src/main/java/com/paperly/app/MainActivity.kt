package com.paperly.app

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
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
import com.paperly.app.ui.update.UpdateDialog
import com.paperly.app.ui.update.UpdateViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val app = application as PaperlyApp
        val crashReport = app.takeCrashReport()

        setContent {
            PaperlyTheme {
                var report by remember { mutableStateOf(crashReport) }
                report?.let { text -> CrashReportDialog(text, onDismiss = { report = null }) }
                val updateVm = paperlyViewModel("update") { UpdateViewModel(app.updater) }
                LaunchedEffect(Unit) { updateVm.autoCheck() }
                UpdateDialog(updateVm)
                val session by app.sessionStore.session.collectAsStateWithLifecycle()
                AnimatedContent(targetState = session.isLoggedIn, transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "auth") { loggedIn ->
                    if (loggedIn) {
                        MainNavigation(app, onCheckUpdates = updateVm::manualCheck)
                    } else {
                        LoginScreen(paperlyViewModel(key = "login") { LoginViewModel(app.repository, app.sessionStore) })
                    }
                }
            }
        }
    }
}

@Composable
private fun CrashReportDialog(report: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Paperly closed unexpectedly") },
        text = {
            Column {
                Text("Sorry about that. Please share this report so it can be fixed.")
                Spacer(Modifier.height(12.dp))
                Text(
                    report,
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.heightIn(max = 260.dp).verticalScroll(rememberScrollState())
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val send = Intent(Intent.ACTION_SEND).setType("text/plain")
                    .putExtra(Intent.EXTRA_SUBJECT, "Paperly crash report")
                    .putExtra(Intent.EXTRA_TEXT, report)
                runCatching { context.startActivity(Intent.createChooser(send, "Share crash report")) }
                onDismiss()
            }) { Text("Share report") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Close") } }
    )
}

@Composable
inline fun <reified VM : ViewModel> paperlyViewModel(key: String, crossinline create: () -> VM): VM =
    viewModel(key = key, factory = viewModelFactory { initializer { create() } })

@Composable
private fun MainNavigation(app: PaperlyApp, onCheckUpdates: () -> Unit) {
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
                onOpenPaper = { id, _ -> nav.navigate("paper/$id") },
                onCheckUpdates = onCheckUpdates
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
