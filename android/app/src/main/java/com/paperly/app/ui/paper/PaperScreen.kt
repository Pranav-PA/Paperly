package com.paperly.app.ui.paper

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.paperly.app.data.PaperlyException
import com.paperly.app.data.PaperlyRepository
import com.paperly.app.data.PaperlyRepository.ExportKind
import com.paperly.app.data.model.Paper
import com.paperly.app.data.model.PaperVersion
import com.paperly.app.data.model.Question
import com.paperly.app.ui.components.*
import com.paperly.app.ui.theme.*
import com.paperly.app.util.Files
import kotlinx.coroutines.launch
import java.io.File

class PaperViewModel(private val repo: PaperlyRepository, val paperId: String) : ViewModel() {
    var paper by mutableStateOf<Paper?>(null)
        private set
    var loading by mutableStateOf(true)
        private set
    var loadError by mutableStateOf<String?>(null)
        private set
    var editing by mutableStateOf(false)
        private set
    var versions by mutableStateOf<List<PaperVersion>>(emptyList())
        private set
    var exporting by mutableStateOf(false)
        private set

    /** One-shot messages for the snackbar. */
    var notice by mutableStateOf<String?>(null)

    init { load() }

    fun load() {
        loading = true
        viewModelScope.launch {
            try {
                paper = repo.paper(paperId)
                loadError = null
            } catch (e: PaperlyException) {
                loadError = e.message
            } finally {
                loading = false
            }
        }
    }

    fun edit(instruction: String, onFailed: (String) -> Unit) {
        editing = true
        viewModelScope.launch {
            try {
                val result = repo.editPaper(paperId, instruction)
                paper = result.paper
                notice = "Version ${result.versionNumber}: ${result.changeSummary}"
            } catch (e: PaperlyException) {
                notice = e.message
                onFailed(instruction)
            } finally {
                editing = false
            }
        }
    }

    fun loadVersions() = viewModelScope.launch {
        versions = try { repo.versions(paperId) } catch (e: PaperlyException) { notice = e.message; emptyList() }
    }

    fun revert(version: Int) = viewModelScope.launch {
        try {
            repo.revert(paperId, version)
            paper = repo.paper(paperId)
            notice = "Restored version $version"
        } catch (e: PaperlyException) {
            notice = e.message
        }
    }

    fun export(kind: ExportKind, format: String, then: (File) -> Unit) {
        val title = paper?.metadata?.title ?: "Paper"
        exporting = true
        viewModelScope.launch {
            try {
                then(repo.export(paperId, title, kind, format))
            } catch (e: PaperlyException) {
                notice = e.message
            } finally {
                exporting = false
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PaperScreen(vm: PaperViewModel, onBack: () -> Unit) {
    var showAnswers by rememberSaveable { mutableStateOf(false) }
    var editText by rememberSaveable { mutableStateOf("") }
    var showExport by remember { mutableStateOf(false) }
    var showVersions by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(vm.notice) {
        vm.notice?.let { snackbar.showSnackbar(it, withDismissAction = true); vm.notice = null }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            TopAppBar(
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back") } },
                title = { Text("Question paper", style = MaterialTheme.typography.titleMedium) },
                actions = {
                    IconButton(onClick = { vm.loadVersions(); showVersions = true }, enabled = vm.paper != null) {
                        Icon(Icons.Rounded.History, "Version history")
                    }
                    FilledTonalButton(
                        onClick = { showExport = true },
                        enabled = vm.paper != null,
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.padding(end = 8.dp)
                    ) {
                        Icon(Icons.Rounded.IosShare, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Export")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background)
            )
        },
        bottomBar = {
            if (vm.paper != null) {
                Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 12.dp) {
                    Column(Modifier.navigationBarsPadding().imePadding()) {
                        if (vm.editing) {
                            LinearProgressIndicator(Modifier.fillMaxWidth())
                            Text(
                                "Applying your change… this can take up to a minute.",
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.padding(start = 20.dp, top = 8.dp)
                            )
                        }
                        Row(Modifier.padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.Bottom) {
                            TextField(
                                value = editText,
                                onValueChange = { editText = it },
                                enabled = !vm.editing,
                                placeholder = { Text("Any change: \"make Q3 harder\", \"two columns\"") },
                                leadingIcon = { Icon(Icons.Rounded.AutoFixHigh, null, tint = MaterialTheme.colorScheme.primary) },
                                shape = RoundedCornerShape(22.dp),
                                colors = TextFieldDefaults.colors(
                                    focusedIndicatorColor = Color.Transparent,
                                    unfocusedIndicatorColor = Color.Transparent,
                                    disabledIndicatorColor = Color.Transparent,
                                    focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                                    unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                                    disabledContainerColor = MaterialTheme.colorScheme.surfaceVariant
                                ),
                                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                                maxLines = 4,
                                modifier = Modifier.weight(1f)
                            )
                            Spacer(Modifier.width(6.dp))
                            FilledIconButton(
                                onClick = {
                                    val text = editText.trim()
                                    editText = ""
                                    vm.edit(text) { failed -> if (editText.isBlank()) editText = failed }
                                },
                                enabled = editText.isNotBlank() && !vm.editing,
                                modifier = Modifier.size(52.dp),
                                shape = CircleShape
                            ) { Icon(Icons.AutoMirrored.Rounded.Send, "Apply change") }
                        }
                    }
                }
            }
        }
    ) { padding ->
        val paper = vm.paper
        when {
            vm.loading && paper == null -> Box(Modifier.fillMaxSize().padding(padding), Alignment.Center) { CircularProgressIndicator() }
            paper == null -> Box(Modifier.fillMaxSize().padding(padding), Alignment.Center) {
                EmptyState(Icons.Rounded.CloudOff, "Couldn't load the paper", vm.loadError ?: "") {
                    Button(onClick = vm::load) { Text("Try again") }
                }
            }
            else -> LazyColumn(
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                modifier = Modifier.fillMaxSize().padding(padding)
            ) {
                item { PaperHeader(paper) }
                item {
                    Surface(shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.surface) {
                        Row(
                            Modifier.fillMaxWidth().clickable { showAnswers = !showAnswers }.padding(horizontal = 16.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Rounded.Key, null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(Modifier.width(12.dp))
                            Column(Modifier.weight(1f)) {
                                Text("Show answers & solutions", style = MaterialTheme.typography.titleSmall)
                                Text("Tap a question to target it for an edit", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Switch(checked = showAnswers, onCheckedChange = { showAnswers = it })
                        }
                    }
                }
                paper.sections.forEachIndexed { si, section ->
                    item(key = "sec-$si") {
                        Column(Modifier.padding(top = 10.dp, start = 4.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(section.title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                                section.totalMarks?.let { Pill("${formatMarks(it)} marks", MaterialTheme.colorScheme.primary) }
                            }
                            section.instructions?.let {
                                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 2.dp))
                            }
                        }
                    }
                    itemsIndexed(section.questions, key = { qi, _ -> "q-$si-$qi" }) { _, q ->
                        QuestionCard(q, showAnswers) {
                            if (!vm.editing) editText = "Q${q.number}: "
                        }
                    }
                }
            }
        }
    }

    if (showExport) {
        ExportSheet(vm, onDismiss = { showExport = false })
    }
    if (showVersions) {
        ModalBottomSheet(onDismissRequest = { showVersions = false }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
            Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
                Text("Version history", style = MaterialTheme.typography.titleLarge)
                Text("Every change is saved. Restore any version.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(12.dp))
                if (vm.versions.isEmpty()) {
                    Box(Modifier.fillMaxWidth().padding(24.dp), Alignment.Center) { CircularProgressIndicator() }
                }
                vm.versions.forEach { v ->
                    Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            Modifier.size(38.dp).clip(CircleShape)
                                .background(if (v.isActive) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("v${v.versionNumber}", style = MaterialTheme.typography.labelMedium,
                                color = if (v.isActive) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(v.changeSummary ?: "Version ${v.versionNumber}", style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Text(relativeTime(v.createdAt), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if (v.isActive) {
                            Pill("Current", Success)
                        } else {
                            TextButton(onClick = { vm.revert(v.versionNumber); showVersions = false }) { Text("Restore") }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PaperHeader(paper: Paper) {
    val meta = paper.metadata
    Box(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(26.dp))
            .background(LocalPaperlyExtras.current.heroGradient)
            .padding(20.dp)
    ) {
        Column {
            meta.institutionName?.let {
                Text(it.uppercase(), style = MaterialTheme.typography.labelSmall, color = Color.White.copy(alpha = 0.8f))
                Spacer(Modifier.height(4.dp))
            }
            Text(meta.title, style = MaterialTheme.typography.headlineSmall, color = Color.White)
            meta.subtitle?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = Color.White.copy(alpha = 0.85f)) }
            Spacer(Modifier.height(14.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                meta.subject.takeIf { it.isNotBlank() }?.let { Pill(it, Color.White) }
                meta.classGrade?.takeIf { it.isNotBlank() }?.let { Pill(it, Color.White) }
            }
            paper.layout?.summary?.takeIf { it.isNotBlank() }?.let {
                Spacer(Modifier.height(8.dp))
                Pill(it, Color.White, icon = Icons.Rounded.ViewColumn)
            }
            Spacer(Modifier.height(16.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                HeaderStat(Icons.Rounded.Grade, formatMarks(meta.totalMarks), "Marks")
                HeaderStat(Icons.Rounded.Quiz, paper.questionCount.toString(), "Questions")
                HeaderStat(Icons.Rounded.Timer, "${meta.durationMinutes}", "Minutes")
            }
        }
    }
}

@Composable
private fun HeaderStat(icon: ImageVector, value: String, label: String) {
    Row(
        Modifier.clip(RoundedCornerShape(16.dp)).background(Color.White.copy(alpha = 0.14f)).padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, null, tint = Color.White, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(6.dp))
        Column {
            Text(value, style = MaterialTheme.typography.titleSmall, color = Color.White)
            Text(label, style = MaterialTheme.typography.labelSmall, color = Color.White.copy(alpha = 0.8f))
        }
    }
}

private fun difficultyColor(d: String?) = when (d?.lowercase()) {
    "easy" -> Success
    "hard" -> Danger
    else -> Warning
}

private fun typeLabel(type: String) = when (type) {
    "mcq" -> "MCQ"
    "multi_select" -> "Multi-select"
    "numerical" -> "Numerical"
    "assertion_reason" -> "Assertion-Reason"
    "short_answer" -> "Short answer"
    "long_answer" -> "Long answer"
    "match_the_following" -> "Match"
    "case_study" -> "Case study"
    else -> type.replace('_', ' ').replaceFirstChar { it.uppercase() }
}

@Composable
private fun QuestionCard(q: Question, showAnswers: Boolean, onTap: () -> Unit) {
    var solutionOpen by remember(q.id, q.text) { mutableStateOf(false) }
    val correctLabels = remember(q.answerKey) {
        q.answerKey.orEmpty().uppercase().split(',', ' ', '&', '/').map { it.trim().trim('(', ')', '.') }.filter { it.length == 1 }.toSet()
    }
    Surface(
        onClick = onTap,
        shape = RoundedCornerShape(22.dp),
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 1.dp,
        modifier = Modifier.fillMaxWidth().animateContentSize()
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.size(34.dp).clip(RoundedCornerShape(11.dp)).background(LocalPaperlyExtras.current.brandGradient),
                    contentAlignment = Alignment.Center
                ) { Text("${q.number}", style = MaterialTheme.typography.labelLarge, color = Color.White) }
                Spacer(Modifier.width(10.dp))
                Pill(typeLabel(q.type), MaterialTheme.colorScheme.secondary)
                Spacer(Modifier.width(6.dp))
                q.difficulty?.let { Pill(it.replaceFirstChar { c -> c.uppercase() }, difficultyColor(it)) }
                Spacer(Modifier.weight(1f))
                Text("${formatMarks(q.marks)} mark${if (q.marks == 1.0) "" else "s"}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            }
            Spacer(Modifier.height(12.dp))
            Text(q.text, style = MaterialTheme.typography.bodyLarge)
            q.options?.takeIf { it.isNotEmpty() }?.let { options ->
                Spacer(Modifier.height(10.dp))
                options.forEach { opt ->
                    val correct = showAnswers && opt.label.uppercase() in correctLabels
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(vertical = 3.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .background(if (correct) Success.copy(alpha = 0.12f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
                            .then(if (correct) Modifier.border(BorderStroke(1.dp, Success.copy(alpha = 0.5f)), RoundedCornerShape(14.dp)) else Modifier)
                            .padding(horizontal = 12.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("${opt.label}.", style = MaterialTheme.typography.labelLarge, color = if (correct) Success else MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.width(10.dp))
                        Text(opt.text, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                        if (correct) Icon(Icons.Rounded.CheckCircle, null, tint = Success, modifier = Modifier.size(18.dp))
                    }
                }
            }
            AnimatedVisibility(showAnswers && (q.answerKey != null || q.detailedSolution != null)) {
                Column(Modifier.padding(top = 12.dp)) {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    Spacer(Modifier.height(10.dp))
                    q.answerKey?.let {
                        Row {
                            Text("Answer  ", style = MaterialTheme.typography.labelLarge, color = Success)
                            Text(it, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                    q.detailedSolution?.let { sol ->
                        TextButton(onClick = { solutionOpen = !solutionOpen }, contentPadding = PaddingValues(0.dp)) {
                            Text(if (solutionOpen) "Hide solution" else "Show step-by-step solution")
                        }
                        if (solutionOpen) {
                            Text(sol, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ExportSheet(vm: PaperViewModel, onDismiss: () -> Unit) {
    val context = LocalContext.current
    var kind by remember { mutableStateOf(ExportKind.PAPER) }
    var format by remember { mutableStateOf("pdf") }

    fun run(action: (File) -> Unit) = vm.export(kind, format, action)

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
            Text("Export", style = MaterialTheme.typography.titleLarge)
            Text("Print-ready PDF or editable Word document", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(16.dp))

            listOf(
                Triple(ExportKind.PAPER, "Question paper", "For students; no answers"),
                Triple(ExportKind.SOLUTIONS, "Answer key & solutions", "Step-by-step, for teachers"),
                Triple(ExportKind.PAPER_WITH_ANSWERS, "Paper with answers", "Questions followed by answers"),
            ).forEach { (k, title, subtitle) ->
                val selected = kind == k
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp)
                        .clip(RoundedCornerShape(16.dp))
                        .border(1.5.dp, if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(16.dp))
                        .background(if (selected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f) else Color.Transparent)
                        .clickable { kind = k }
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    RadioButton(selected = selected, onClick = { kind = k })
                    Column {
                        Text(title, style = MaterialTheme.typography.titleSmall)
                        Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf("pdf" to "PDF", "docx" to "Word (DOCX)").forEachIndexed { i, (value, label) ->
                    SegmentedButton(
                        selected = format == value,
                        onClick = { format = value },
                        shape = SegmentedButtonDefaults.itemShape(i, 2)
                    ) { Text(label) }
                }
            }
            Spacer(Modifier.height(18.dp))
            if (vm.exporting) {
                LinearProgressIndicator(Modifier.fillMaxWidth().padding(bottom = 12.dp))
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(
                    onClick = {
                        run { file ->
                            if (!Files.open(context, file)) vm.notice = "No app to open this file. Use Share or Save instead."
                        }
                    },
                    enabled = !vm.exporting,
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.weight(1f).height(50.dp)
                ) {
                    Icon(Icons.AutoMirrored.Rounded.OpenInNew, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Open")
                }
                FilledTonalButton(
                    onClick = { run { Files.share(context, it) } },
                    enabled = !vm.exporting,
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.weight(1f).height(50.dp)
                ) {
                    Icon(Icons.Rounded.Share, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Share")
                }
            }
            if (Files.canSaveToDownloads) {
                OutlinedButton(
                    onClick = {
                        run { file ->
                            vm.notice = try { "Saved to ${Files.saveToDownloads(context, file)}" } catch (e: Exception) { "Couldn't save: ${e.message}" }
                        }
                    },
                    enabled = !vm.exporting,
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(50.dp)
                ) {
                    Icon(Icons.Rounded.Download, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Save to Downloads")
                }
            }
        }
    }
}
