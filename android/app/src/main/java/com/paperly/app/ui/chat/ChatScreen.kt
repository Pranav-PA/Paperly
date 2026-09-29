package com.paperly.app.ui.chat

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.paperly.app.data.PaperlyException
import com.paperly.app.data.PaperlyRepository
import com.paperly.app.data.model.Message
import com.paperly.app.ui.components.BrandMark
import com.paperly.app.ui.components.ErrorBanner
import com.paperly.app.ui.components.TypingIndicator
import com.paperly.app.ui.theme.LocalPaperlyExtras
import com.paperly.app.ui.theme.Success
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class ChatViewModel(
    private val repo: PaperlyRepository,
    private val conversationId: String,
    initialPrompt: String?
) : ViewModel() {
    var title by mutableStateOf("New paper")
        private set
    var messages by mutableStateOf<List<Message>>(emptyList())
        private set
    var latestPaperId by mutableStateOf<String?>(null)
        private set
    var loading by mutableStateOf(true)
        private set
    var sending by mutableStateOf(false)
        private set
    var generating by mutableStateOf(false)
        private set
    var uploading by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
    /** Text of a message that failed to send, handed back to the input box. */
    var restoredDraft by mutableStateOf<String?>(null)

    init {
        viewModelScope.launch {
            load()
            loading = false
            if (!initialPrompt.isNullOrBlank() && messages.isEmpty()) send(initialPrompt)
        }
    }

    private suspend fun load() {
        try {
            val detail = repo.conversation(conversationId)
            title = detail.title
            messages = detail.messages
            latestPaperId = detail.latestPaperId
            if (detail.activeJobId != null && !generating) {
                viewModelScope.launch { followJob(detail.activeJobId) }
            }
        } catch (e: PaperlyException) {
            error = e.message
        }
    }

    fun refresh() = viewModelScope.launch { load() }

    fun metaAction(message: Message) = repo.metaOf(message)

    fun send(text: String) {
        val content = text.trim()
        if (content.isEmpty() || sending || generating) return
        val optimistic = Message("local-${System.nanoTime()}", "user", content, null, "")
        messages = messages + optimistic
        sending = true
        error = null
        viewModelScope.launch {
            try {
                val reply = repo.sendMessage(conversationId, content)
                load()
                val meta = repo.metaOf(reply)
                if (meta?.action == "generating" && meta.jobId != null) followJob(meta.jobId)
            } catch (e: PaperlyException) {
                messages = messages - optimistic
                restoredDraft = content
                error = e.message
            } finally {
                sending = false
            }
        }
    }

    private suspend fun followJob(jobId: String) {
        if (generating) return
        generating = true
        try {
            repo.awaitJob(jobId)
        } catch (e: PaperlyException) {
            error = e.message
        } finally {
            load()
            generating = false
        }
    }

    fun upload(uri: Uri) {
        uploading = true
        error = null
        viewModelScope.launch {
            try {
                repo.upload(conversationId, uri)
                load()
            } catch (e: PaperlyException) {
                error = e.message
            } finally {
                uploading = false
            }
        }
    }
}

private val uploadTypes = arrayOf(
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "text/csv",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(vm: ChatViewModel, onBack: () -> Unit, onOpenPaper: (String, String) -> Unit) {
    var input by rememberSaveable { mutableStateOf("") }
    val listState = rememberLazyListState()
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(vm::upload) }

    LaunchedEffect(vm.restoredDraft) {
        vm.restoredDraft?.let { if (input.isBlank()) input = it; vm.restoredDraft = null }
    }
    val extraItems = (if (vm.sending) 1 else 0) + (if (vm.generating) 1 else 0)
    LaunchedEffect(vm.messages.size, extraItems) {
        val total = vm.messages.size + extraItems
        if (total > 0) listState.animateScrollToItem(total - 1)
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back") } },
                title = {
                    Column {
                        Text(vm.title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(
                            when {
                                vm.generating -> "Writing your paper…"
                                vm.sending -> "Thinking…"
                                else -> "Paperly AI assistant"
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                actions = {
                    vm.latestPaperId?.let { id ->
                        FilledTonalButton(
                            onClick = { onOpenPaper(id, vm.title) },
                            shape = RoundedCornerShape(12.dp),
                            contentPadding = PaddingValues(horizontal = 12.dp),
                            modifier = Modifier.padding(end = 8.dp)
                        ) {
                            Icon(Icons.Rounded.Description, null, Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("Paper")
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background)
            )
        },
        bottomBar = {
            Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 12.dp) {
                Column(Modifier.navigationBarsPadding().imePadding()) {
                    vm.error?.let {
                        ErrorBanner(it, Modifier.padding(start = 12.dp, end = 12.dp, top = 10.dp))
                    }
                    if (vm.uploading) {
                        Row(Modifier.padding(start = 20.dp, top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(14.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("Uploading reference file…", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    Row(Modifier.padding(horizontal = 8.dp, vertical = 8.dp), verticalAlignment = Alignment.Bottom) {
                        IconButton(onClick = { picker.launch(uploadTypes) }, enabled = !vm.uploading && !vm.generating) {
                            Icon(Icons.Rounded.AttachFile, contentDescription = "Attach syllabus or notes")
                        }
                        TextField(
                            value = input,
                            onValueChange = { input = it },
                            placeholder = { Text(if (vm.latestPaperId != null) "Ask for another version…" else "Reply to Paperly…") },
                            shape = RoundedCornerShape(22.dp),
                            colors = TextFieldDefaults.colors(
                                focusedIndicatorColor = Color.Transparent,
                                unfocusedIndicatorColor = Color.Transparent,
                                disabledIndicatorColor = Color.Transparent,
                                focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                                unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant
                            ),
                            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                            maxLines = 5,
                            modifier = Modifier.weight(1f)
                        )
                        Spacer(Modifier.width(6.dp))
                        val canSend = input.isNotBlank() && !vm.sending && !vm.generating
                        FilledIconButton(
                            onClick = { vm.send(input); input = "" },
                            enabled = canSend,
                            modifier = Modifier.size(52.dp),
                            shape = CircleShape
                        ) {
                            Icon(Icons.AutoMirrored.Rounded.Send, contentDescription = "Send")
                        }
                    }
                }
            }
        }
    ) { padding ->
        if (vm.loading) {
            Box(Modifier.fillMaxSize().padding(padding), Alignment.Center) { CircularProgressIndicator() }
            return@Scaffold
        }
        LazyColumn(
            state = listState,
            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
            modifier = Modifier.fillMaxSize().padding(padding)
        ) {
            items(vm.messages, key = { it.id }) { msg ->
                val meta = vm.metaAction(msg)
                when {
                    msg.role == "user" -> UserBubble(msg.content)
                    meta?.action == "paper_ready" && meta.paperId != null ->
                        PaperReadyCard(msg.content) { onOpenPaper(meta.paperId, vm.title) }
                    else -> AssistantBubble(msg.content, isError = meta?.action == "error")
                }
            }
            if (vm.sending) {
                item(key = "typing") {
                    AssistantRow { TypingIndicator(Modifier.padding(horizontal = 18.dp, vertical = 16.dp)) }
                }
            }
            if (vm.generating) {
                item(key = "generating") { GeneratingCard() }
            }
        }
    }
}

@Composable
private fun UserBubble(text: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
        Box(
            Modifier
                .widthIn(max = 310.dp)
                .clip(RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp, bottomStart = 22.dp, bottomEnd = 6.dp))
                .background(LocalPaperlyExtras.current.brandGradient)
                .padding(horizontal = 16.dp, vertical = 12.dp)
        ) {
            SelectionContainer { Text(text, color = Color.White, style = MaterialTheme.typography.bodyLarge) }
        }
    }
}

@Composable
private fun AssistantRow(content: @Composable () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
        BrandMark(size = 30.dp)
        Spacer(Modifier.width(8.dp))
        Surface(
            shape = RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp, bottomStart = 6.dp, bottomEnd = 22.dp),
            color = MaterialTheme.colorScheme.surface,
            shadowElevation = 1.dp,
            modifier = Modifier.widthIn(max = 310.dp)
        ) { content() }
    }
}

@Composable
private fun AssistantBubble(text: String, isError: Boolean) {
    AssistantRow {
        SelectionContainer {
            Text(
                text,
                style = MaterialTheme.typography.bodyLarge,
                color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)
            )
        }
    }
}

@Composable
private fun PaperReadyCard(text: String, onOpen: () -> Unit) {
    AnimatedVisibility(visible = true, enter = fadeIn() + slideInVertically { it / 3 }) {
        Surface(
            shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.surface,
            shadowElevation = 3.dp,
            modifier = Modifier.fillMaxWidth().padding(start = 38.dp)
        ) {
            Column(Modifier.padding(18.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier.size(40.dp).clip(RoundedCornerShape(12.dp)).background(Success.copy(alpha = 0.14f)),
                        contentAlignment = Alignment.Center
                    ) { Icon(Icons.Rounded.TaskAlt, null, tint = Success) }
                    Spacer(Modifier.width(12.dp))
                    Text("Paper ready", style = MaterialTheme.typography.titleMedium)
                }
                Spacer(Modifier.height(10.dp))
                Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(14.dp))
                Button(onClick = onOpen, shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Rounded.MenuBook, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Open paper")
                }
            }
        }
    }
}

private val generationSteps = listOf(
    0 to "Understanding your requirements",
    6 to "Drafting questions",
    25 to "Checking answers & calculations",
    50 to "Formatting the paper",
)

@Composable
private fun GeneratingCard() {
    var elapsed by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) { delay(1000); elapsed++ }
    }
    val current = generationSteps.indexOfLast { elapsed >= it.first }

    Surface(
        shape = RoundedCornerShape(24.dp),
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 3.dp,
        modifier = Modifier.fillMaxWidth().padding(start = 38.dp)
    ) {
        Column(Modifier.padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Rounded.AutoAwesome, null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(10.dp))
                Text("Writing your paper", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                Text("${elapsed}s", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(12.dp))
            LinearProgressIndicator(Modifier.fillMaxWidth().clip(RoundedCornerShape(50)))
            Spacer(Modifier.height(14.dp))
            generationSteps.forEachIndexed { i, (_, label) ->
                Row(Modifier.padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                    when {
                        i < current -> Icon(Icons.Rounded.CheckCircle, null, tint = Success, modifier = Modifier.size(20.dp))
                        i == current -> CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(18.dp).padding(1.dp))
                        else -> Icon(Icons.Rounded.RadioButtonUnchecked, null, tint = MaterialTheme.colorScheme.outline, modifier = Modifier.size(20.dp))
                    }
                    Spacer(Modifier.width(12.dp))
                    Text(
                        label,
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (i <= current) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Spacer(Modifier.height(6.dp))
            Text(
                "You can leave this screen; the paper keeps generating on the server.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
