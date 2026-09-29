package com.paperly.app.ui.navigation

import androidx.compose.runtime.*
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.paperly.app.data.local.entity.ConversationEntity
import com.paperly.app.data.local.entity.MessageEntity
import com.paperly.app.data.local.entity.PaperEntity
import com.paperly.app.data.remote.dto.PaperSchemaDto
import com.paperly.app.data.repository.AuthRepository
import com.paperly.app.data.repository.ConversationRepository
import com.paperly.app.data.repository.PaperRepository
import com.paperly.app.ui.screens.chat.ChatScreen
import com.paperly.app.ui.screens.editor.DocumentEditorScreen
import com.paperly.app.ui.screens.export.ExportScreen
import com.paperly.app.ui.screens.history.HistoryScreen
import com.paperly.app.ui.screens.home.HomeScreen
import com.paperly.app.ui.screens.login.LoginScreen
import com.paperly.app.ui.screens.progress.GenerationProgressScreen
import kotlinx.coroutines.launch

@Composable
fun PaperlyNavGraph(
    navController: NavHostController,
    authRepo: AuthRepository,
    convRepo: ConversationRepository,
    paperRepo: PaperRepository
) {
    val coroutineScope = rememberCoroutineScope()
    val activeUser by authRepo.getActiveUser().collectAsState(initial = null)
    val startDestination = if (activeUser != null) Screen.Home.route else Screen.Login.route

    NavHost(navController = navController, startDestination = startDestination) {

        // 1. Login Screen
        composable(Screen.Login.route) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Screen.Home.route) {
                        popUpTo(Screen.Login.route) { inclusive = true }
                    }
                },
                onLoginClick = { username, password, callback ->
                    coroutineScope.launch {
                        val result = authRepo.login(username, password)
                        if (result.isSuccess) {
                            callback(true, null)
                        } else {
                            callback(false, result.exceptionOrNull()?.message)
                        }
                    }
                }
            )
        }

        // 2. Home Screen
        composable(Screen.Home.route) {
            val conversations by convRepo.getLocalConversations().collectAsState(initial = emptyList())

            LaunchedEffect(Unit) {
                convRepo.refreshConversations()
            }

            HomeScreen(
                conversations = conversations,
                onNewConversation = { prompt ->
                    coroutineScope.launch {
                        val result = convRepo.createConversation(prompt.take(30) + "...")
                        if (result.isSuccess) {
                            val conv = result.getOrNull()!!
                            convRepo.sendMessage(conv.id, prompt)
                            navController.navigate(Screen.Chat.createRoute(conv.id))
                        }
                    }
                },
                onSelectConversation = { convId ->
                    navController.navigate(Screen.Chat.createRoute(convId))
                },
                onViewHistory = {
                    navController.navigate(Screen.History.route)
                }
            )
        }

        // 3. Chat Screen
        composable(
            route = Screen.Chat.route,
            arguments = listOf(navArgument("conversationId") { type = NavType.StringType })
        ) { backStackEntry ->
            val convId = backStackEntry.arguments?.getString("conversationId") ?: ""
            val messages by convRepo.getLocalMessages(convId).collectAsState(initial = emptyList())
            val conversations by convRepo.getLocalConversations().collectAsState(initial = emptyList())
            val currentConv = conversations.firstOrNull { it.id == convId }

            ChatScreen(
                conversationTitle = currentConv?.title ?: "New Assessment",
                messages = messages,
                latestPaperId = currentConv?.latestPaperId,
                onBack = { navController.popBackStack() },
                onSendMessage = { text ->
                    coroutineScope.launch {
                        convRepo.sendMessage(convId, text)
                    }
                },
                onOpenEditor = { paperId ->
                    navController.navigate(Screen.Editor.createRoute(paperId))
                },
                onUploadClick = {
                    // File picker trigger in production
                }
            )
        }

        // 4. Progress Screen
        composable(
            route = Screen.Progress.route,
            arguments = listOf(navArgument("conversationId") { type = NavType.StringType })
        ) {
            GenerationProgressScreen()
        }

        // 5. Document Editor Screen
        composable(
            route = Screen.Editor.route,
            arguments = listOf(navArgument("paperId") { type = NavType.StringType })
        ) { backStackEntry ->
            val paperId = backStackEntry.arguments?.getString("paperId") ?: ""
            var paperSchema by remember { mutableStateOf<PaperSchemaDto?>(null) }
            var isLoading by remember { mutableStateOf(true) }

            LaunchedEffect(paperId) {
                isLoading = true
                val result = paperRepo.fetchPaper(paperId)
                if (result.isSuccess) {
                    paperSchema = result.getOrNull()
                }
                isLoading = false
            }

            DocumentEditorScreen(
                paperSchema = paperSchema,
                isLoading = isLoading,
                onBack = { navController.popBackStack() },
                onNavigateToExport = {
                    navController.navigate(Screen.Export.createRoute(paperId))
                },
                onApplyEdit = { editInstruction ->
                    coroutineScope.launch {
                        isLoading = true
                        val editRes = paperRepo.editPaper(paperId, editInstruction)
                        if (editRes.isSuccess) {
                            paperSchema = editRes.getOrNull()
                        }
                        isLoading = false
                    }
                }
            )
        }

        // 6. Export Screen
        composable(
            route = Screen.Export.route,
            arguments = listOf(navArgument("paperId") { type = NavType.StringType })
        ) { backStackEntry ->
            val paperId = backStackEntry.arguments?.getString("paperId") ?: ""

            ExportScreen(
                paperTitle = "Export Assessment",
                onBack = { navController.popBackStack() },
                onExport = { format, includeSolutions, callback ->
                    coroutineScope.launch {
                        val result = paperRepo.downloadExport(
                            context = navController.context,
                            paperId = paperId,
                            format = format,
                            includeAnswers = includeSolutions
                        )
                        if (result.isSuccess) {
                            callback(true, result.getOrNull()?.absolutePath)
                        } else {
                            callback(false, result.exceptionOrNull()?.message)
                        }
                    }
                }
            )
        }

        // 7. History Screen
        composable(Screen.History.route) {
            val papers by paperRepo.getAllLocalPapers().collectAsState(initial = emptyList())

            HistoryScreen(
                papers = papers,
                onBack = { navController.popBackStack() },
                onSelectPaper = { paperId ->
                    navController.navigate(Screen.Editor.createRoute(paperId))
                }
            )
        }
    }
}
