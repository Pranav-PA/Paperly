package com.paperly.app.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Logout
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.*
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.paperly.app.data.PaperlyException
import com.paperly.app.data.PaperlyRepository
import com.paperly.app.data.SessionStore
import com.paperly.app.data.model.ConversationSummary
import com.paperly.app.data.model.PaperSummary
import com.paperly.app.ui.components.*
import com.paperly.app.ui.theme.LocalPaperlyExtras
import com.paperly.app.ui.theme.Success
import com.paperly.app.ui.theme.Warning
import kotlinx.coroutines.launch
import java.time.LocalTime

class HomeViewModel(private val repo: PaperlyRepository, private val store: SessionStore) : ViewModel() {
    var conversations by mutableStateOf<List<ConversationSummary>>(emptyList())
        private set
    var papers by mutableStateOf<List<PaperSummary>>(emptyList())
        private set
    var refreshing by mutableStateOf(false)
        private set
    var loadedOnce by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
    var creating by mutableStateOf(false)
        private set

    val session = store.session

    fun refresh() {
        refreshing = true
        viewModelScope.launch {
            try {
                conversations = repo.conversations()
                papers = repo.papers()
                error = null
            } catch (e: PaperlyException) {
                error = e.message
            } finally {
                refreshing = false
                loadedOnce = true
            }
        }
    }

    fun startConversation(prompt: String, onCreated: (String) -> Unit) {
        creating = true
        viewModelScope.launch {
            try {
                val conv = repo.createConversation(prompt)
                onCreated(conv.id)
            } catch (e: PaperlyException) {
                error = e.message
            } finally {
                creating = false
            }
        }
    }

    fun delete(conv: ConversationSummary) {
        conversations = conversations - conv
        papers = papers.filterNot { it.conversationId == conv.id }
        viewModelScope.launch {
            try {
                repo.deleteConversation(conv.id)
            } catch (e: PaperlyException) {
                error = e.message
                refresh()
            }
        }
    }

    suspend fun changePassword(current: String, new: String): String? = try {
        repo.changePassword(current, new)
        null
    } catch (e: PaperlyException) {
        e.message
    }

    fun logout() = repo.logout()
}

private val suggestions = listOf(
    "Class 10 Maths: Quadratic Equations, 40 marks",
    "NEET Physics mock: Electrostatics, 45 MCQs",
    "Class 8 Science unit test on Light, 25 marks",
    "Class 12 Chemistry: Chemical Kinetics, 35 marks",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    vm: HomeViewModel,
    onOpenConversation: (id: String, initialPrompt: String?) -> Unit,
    onOpenPaper: (paperId: String, title: String) -> Unit,
    onCheckUpdates: () -> Unit,
) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var menuOpen by remember { mutableStateOf(false) }
    var showPasswordDialog by remember { mutableStateOf(false) }
    var pendingDelete by remember { mutableStateOf<ConversationSummary?>(null) }

    val session by vm.session.collectAsStateWithLifecycle()
    val displayName = session.displayName

    LaunchedEffect(Unit) { vm.refresh() }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            Row(
                Modifier
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .padding(start = 20.dp, end = 12.dp, top = 12.dp, bottom = 6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                BrandMark(size = 40.dp)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(greeting(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(displayName, style = MaterialTheme.typography.titleLarge, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Box {
                    IconButton(onClick = { menuOpen = true }) {
                        Box(
                            Modifier.size(38.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primaryContainer),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                displayName.take(1).uppercase(),
                                style = MaterialTheme.typography.titleSmall,
                                color = MaterialTheme.colorScheme.onPrimaryContainer
                            )
                        }
                    }
                    DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }, shape = RoundedCornerShape(16.dp)) {
                        DropdownMenuItem(
                            text = { Text("Change password") },
                            leadingIcon = { Icon(Icons.Rounded.Key, null) },
                            onClick = { menuOpen = false; showPasswordDialog = true }
                        )
                        DropdownMenuItem(
                            text = { Text("Check for updates") },
                            leadingIcon = { Icon(Icons.Rounded.SystemUpdate, null) },
                            onClick = { menuOpen = false; onCheckUpdates() }
                        )
                        DropdownMenuItem(
                            text = { Text("Sign out") },
                            leadingIcon = { Icon(Icons.AutoMirrored.Rounded.Logout, null) },
                            onClick = { menuOpen = false; vm.logout() }
                        )
                    }
                }
            }
        },
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface, tonalElevation = 0.dp) {
                NavigationBarItem(
                    selected = tab == 0, onClick = { tab = 0 },
                    icon = { Icon(Icons.Rounded.AutoAwesome, null) }, label = { Text("Create") }
                )
                NavigationBarItem(
                    selected = tab == 1, onClick = { tab = 1 },
                    icon = { Icon(Icons.Rounded.LibraryBooks, null) }, label = { Text("Library") }
                )
            }
        }
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = vm.refreshing && vm.loadedOnce,
            onRefresh = vm::refresh,
            modifier = Modifier.padding(padding).fillMaxSize()
        ) {
            if (tab == 0) {
                CreateTab(vm, onOpenConversation, onDelete = { pendingDelete = it })
            } else {
                LibraryTab(vm, onOpenPaper)
            }
        }
    }

    pendingDelete?.let { conv ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            icon = { Icon(Icons.Rounded.DeleteOutline, null) },
            title = { Text("Delete this chat?") },
            text = { Text("\"${conv.title}\" and its paper will be permanently deleted.") },
            confirmButton = {
                TextButton(onClick = { vm.delete(conv); pendingDelete = null }) {
                    Text("Delete", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = { TextButton(onClick = { pendingDelete = null }) { Text("Cancel") } }
        )
    }

    if (showPasswordDialog) {
        ChangePasswordDialog(vm, onDismiss = { showPasswordDialog = false })
    }
}

private fun greeting(): String = when (LocalTime.now().hour) {
    in 5..11 -> "Good morning"
    in 12..16 -> "Good afternoon"
    else -> "Good evening"
}

@Composable
private fun CreateTab(
    vm: HomeViewModel,
    onOpenConversation: (String, String?) -> Unit,
    onDelete: (ConversationSummary) -> Unit
) {
    var prompt by rememberSaveable { mutableStateOf("") }
    val extras = LocalPaperlyExtras.current

    fun submit() {
        val text = prompt.trim()
        if (text.isEmpty() || vm.creating) return
        vm.startConversation(text) { id ->
            prompt = ""
            onOpenConversation(id, text)
        }
    }

    LazyColumn(
        contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 8.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxSize()
    ) {
        item {
            Box(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(28.dp))
                    .background(extras.heroGradient)
                    .padding(20.dp)
            ) {
                Column {
                    Pill("AI teaching assistant", Color.White, icon = Icons.Rounded.AutoAwesome)
                    Spacer(Modifier.height(12.dp))
                    Text("What paper shall we\ncreate today?", style = MaterialTheme.typography.headlineSmall, color = Color.White)
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Describe it in your own words. I'll ask if anything's missing.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color.White.copy(alpha = 0.85f)
                    )
                    Spacer(Modifier.height(16.dp))
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(20.dp))
                            .background(MaterialTheme.colorScheme.surface)
                            .padding(start = 6.dp, end = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        TextField(
                            value = prompt,
                            onValueChange = { prompt = it },
                            placeholder = { Text("e.g. Class 9 Biology test on Cells, 30 marks") },
                            colors = TextFieldDefaults.colors(
                                focusedContainerColor = Color.Transparent,
                                unfocusedContainerColor = Color.Transparent,
                                focusedIndicatorColor = Color.Transparent,
                                unfocusedIndicatorColor = Color.Transparent
                            ),
                            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                            maxLines = 4,
                            modifier = Modifier.weight(1f)
                        )
                        FilledIconButton(
                            onClick = ::submit,
                            enabled = prompt.isNotBlank() && !vm.creating,
                            shape = RoundedCornerShape(14.dp)
                        ) {
                            if (vm.creating) {
                                CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(18.dp), color = Color.White)
                            } else {
                                Icon(Icons.AutoMirrored.Rounded.Send, contentDescription = "Start")
                            }
                        }
                    }
                }
            }
        }
        item {
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                suggestions.forEach { s ->
                    SuggestionChip(
                        onClick = { prompt = s },
                        label = { Text(s, style = MaterialTheme.typography.labelMedium) },
                        shape = RoundedCornerShape(50)
                    )
                }
            }
        }
        vm.error?.let { msg ->
            item { ErrorBanner(msg, onRetry = vm::refresh) }
        }
        item {
            Text("Recent", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp))
        }
        if (!vm.loadedOnce) {
            item { Box(Modifier.fillMaxWidth().padding(32.dp), Alignment.Center) { CircularProgressIndicator() } }
        } else if (vm.conversations.isEmpty()) {
            item {
                EmptyState(
                    Icons.Rounded.EditNote,
                    "No papers yet",
                    "Type what you need above or tap a suggestion to create your first question paper."
                )
            }
        } else {
            items(vm.conversations, key = { it.id }) { conv ->
                ConversationCard(conv, onClick = { onOpenConversation(conv.id, null) }, onDelete = { onDelete(conv) })
            }
        }
    }
}

@Composable
private fun ConversationCard(conv: ConversationSummary, onClick: () -> Unit, onDelete: () -> Unit) {
    val ready = conv.latestPaperId != null
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(20.dp),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 0.dp,
        shadowElevation = 1.dp,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(46.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(if (ready) Success.copy(alpha = 0.12f) else MaterialTheme.colorScheme.primaryContainer),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    if (ready) Icons.Rounded.TaskAlt else Icons.Rounded.ChatBubbleOutline,
                    contentDescription = null,
                    tint = if (ready) Success else MaterialTheme.colorScheme.primary
                )
            }
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(conv.title, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Pill(if (ready) "Paper ready" else "In progress", if (ready) Success else Warning)
                    Spacer(Modifier.width(8.dp))
                    Text(relativeTime(conv.updatedAt), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            IconButton(onClick = onDelete) {
                Icon(Icons.Rounded.DeleteOutline, contentDescription = "Delete", tint = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun LibraryTab(vm: HomeViewModel, onOpenPaper: (String, String) -> Unit) {
    LazyColumn(
        contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 8.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxSize()
    ) {
        item {
            Text("Your papers", style = MaterialTheme.typography.headlineSmall)
            Text(
                "${vm.papers.size} paper${if (vm.papers.size == 1) "" else "s"} · tap to view, edit or export",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        vm.error?.let { msg -> item { ErrorBanner(msg, onRetry = vm::refresh) } }
        if (vm.loadedOnce && vm.papers.isEmpty()) {
            item {
                EmptyState(Icons.Rounded.LibraryBooks, "Your library is empty", "Generated papers will appear here.")
            }
        }
        items(vm.papers, key = { it.id }) { p ->
            Surface(
                onClick = { onOpenPaper(p.id, p.title) },
                shape = RoundedCornerShape(22.dp),
                color = MaterialTheme.colorScheme.surface,
                shadowElevation = 1.dp,
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Pill(p.subject ?: "Paper", MaterialTheme.colorScheme.primary)
                        p.classGrade?.let {
                            Spacer(Modifier.width(6.dp))
                            Pill(it, MaterialTheme.colorScheme.secondary)
                        }
                        Spacer(Modifier.weight(1f))
                        Text(relativeTime(p.updatedAt), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Spacer(Modifier.height(10.dp))
                    Text(p.title, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Spacer(Modifier.height(10.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        Stat(Icons.Rounded.Quiz, "${p.questionCount} questions")
                        Stat(Icons.Rounded.Grade, "${formatMarks(p.totalMarks)} marks")
                        Stat(Icons.Rounded.History, "v${p.versionNumber}")
                    }
                }
            }
        }
    }
}

@Composable
private fun Stat(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(16.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.width(4.dp))
        Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ChangePasswordDialog(vm: HomeViewModel, onDismiss: () -> Unit) {
    var current by remember { mutableStateOf("") }
    var new by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    var done by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(if (done) Icons.Rounded.CheckCircle else Icons.Rounded.Key, null) },
        title = { Text(if (done) "Password changed" else "Change password") },
        text = {
            if (done) {
                Text("Use your new password next time you sign in.")
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                    listOf(
                        Triple("Current password", current) { v: String -> current = v },
                        Triple("New password (8+ characters)", new) { v: String -> new = v },
                        Triple("Confirm new password", confirm) { v: String -> confirm = v },
                    ).forEach { (label, value, onChange) ->
                        OutlinedTextField(
                            value = value, onValueChange = onChange, label = { Text(label) },
                            singleLine = true, visualTransformation = PasswordVisualTransformation(),
                            shape = RoundedCornerShape(14.dp)
                        )
                    }
                }
            }
        },
        confirmButton = {
            if (done) {
                TextButton(onClick = onDismiss) { Text("Done") }
            } else {
                TextButton(
                    enabled = !saving && current.isNotEmpty() && new.isNotEmpty(),
                    onClick = {
                        when {
                            new.length < 8 -> error = "New password must be at least 8 characters."
                            new != confirm -> error = "The new passwords don't match."
                            else -> {
                                saving = true
                                scope.launch {
                                    error = vm.changePassword(current, new)
                                    saving = false
                                    done = error == null
                                }
                            }
                        }
                    }
                ) { Text(if (saving) "Saving…" else "Save") }
            }
        },
        dismissButton = { if (!done) TextButton(onClick = onDismiss) { Text("Cancel") } }
    )
}
