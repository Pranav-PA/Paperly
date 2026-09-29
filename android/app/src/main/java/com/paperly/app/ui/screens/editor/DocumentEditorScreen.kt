package com.paperly.app.ui.screens.editor

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.paperly.app.data.remote.dto.PaperSchemaDto
import com.paperly.app.data.remote.dto.QuestionDto
import com.paperly.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DocumentEditorScreen(
    paperSchema: PaperSchemaDto?,
    isLoading: Boolean,
    onBack: () -> Unit,
    onNavigateToExport: () -> Unit,
    onApplyEdit: (String) -> Unit
) {
    var editPrompt by remember { mutableStateOf("") }
    var isEditing by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        paperSchema?.metadata?.title ?: "Document Editor",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = onNavigateToExport) {
                        Icon(Icons.Default.Download, contentDescription = "Export Document", tint = PrimaryBlue)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.White)
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Slate100)
                .padding(padding)
        ) {
            if (paperSchema == null) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = PrimaryBlue)
                }
            } else {
                // Document Sheet Viewer (White Paper Simulation)
                Card(
                    modifier = Modifier
                        .weight(1f)
                        .padding(horizontal = 12.dp, vertical = 8.dp)
                        .fillMaxWidth(),
                    shape = RoundedCornerShape(4.dp),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                ) {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp)
                    ) {
                        // Institution Header
                        item {
                            paperSchema.metadata.institutionName?.let { inst ->
                                Text(
                                    text = inst.uppercase(),
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 14.sp,
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                            Text(
                                text = paperSchema.metadata.title.uppercase(),
                                fontWeight = FontWeight.Bold,
                                fontSize = 12.sp,
                                textAlign = TextAlign.Center,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(top = 2.dp)
                            )
                            paperSchema.metadata.subtitle?.let { sub ->
                                Text(
                                    text = sub,
                                    fontStyle = FontStyle.Italic,
                                    fontSize = 10.sp,
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(bottom = 6.dp)
                                )
                            }

                            // Meta Bar Table
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = "Subject: ${paperSchema.metadata.subject} (${paperSchema.metadata.classGrade ?: ""})",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                                Text(
                                    text = "Max Marks: ${paperSchema.metadata.totalMarks}",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(bottom = 6.dp),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = "Date: ${paperSchema.metadata.date ?: "Session 2026"}",
                                    fontSize = 11.sp
                                )
                                Text(
                                    text = "Time: ${paperSchema.metadata.durationMinutes} Mins",
                                    fontSize = 11.sp
                                )
                            }

                            HorizontalDivider(color = Color.Black, thickness = 1.dp, modifier = Modifier.padding(bottom = 8.dp))

                            // General Instructions
                            if (paperSchema.metadata.generalInstructions.isNotEmpty()) {
                                Text("General Instructions:", fontWeight = FontWeight.Bold, fontSize = 10.sp)
                                paperSchema.metadata.generalInstructions.forEach { inst ->
                                    Text("• $inst", fontSize = 9.5.sp, modifier = Modifier.padding(start = 6.dp, top = 1.dp))
                                }
                                Spacer(modifier = Modifier.height(10.dp))
                            }
                        }

                        // Sections & Questions
                        paperSchema.sections.forEach { section ->
                            item {
                                Text(
                                    text = section.title.uppercase(),
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 11.sp,
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(top = 10.dp, bottom = 4.dp)
                                )
                                section.instructions?.let { inst ->
                                    Text(
                                        text = "($inst)",
                                        fontStyle = FontStyle.Italic,
                                        fontSize = 9.5.sp,
                                        textAlign = TextAlign.Center,
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(bottom = 6.dp)
                                    )
                                }
                            }

                            items(section.questions) { q ->
                                QuestionRowView(q)
                            }
                        }
                    }
                }

                // Bottom Revision Drawer (Conversational AI Editor)
                Surface(
                    color = Color.White,
                    shadowElevation = 6.dp
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Text(
                            text = "Ask Paperly to edit (e.g. \"Replace Q3 with a numerical\", \"Make Q5 harder\")",
                            fontSize = 11.sp,
                            color = TextSecondary,
                            modifier = Modifier.padding(bottom = 4.dp)
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(
                                value = editPrompt,
                                onValueChange = { editPrompt = it },
                                placeholder = { Text("Ask Paperly to modify the paper...", fontSize = 12.sp) },
                                modifier = Modifier.weight(1f),
                                singleLine = true,
                                shape = RoundedCornerShape(8.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            IconButton(
                                onClick = {
                                    if (editPrompt.isNotBlank()) {
                                        val cmd = editPrompt
                                        editPrompt = ""
                                        onApplyEdit(cmd)
                                    }
                                },
                                enabled = editPrompt.isNotBlank() && !isEditing
                            ) {
                                Icon(Icons.Default.Send, contentDescription = "Edit", tint = PrimaryBlue)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun QuestionRowView(q: QuestionDto) {
    Column(modifier = Modifier.padding(vertical = 4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Text(
                text = "Q${q.questionNumber}. ${q.text}",
                fontSize = 10.5.sp,
                fontWeight = FontWeight.Normal,
                modifier = Modifier.weight(1f)
            )
            Text(
                text = "[${q.marks}M]",
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(start = 6.dp)
            )
        }

        // Render MCQ choices if present
        if (!q.options.isNullOrEmpty()) {
            q.options.forEach { opt ->
                Text(
                    text = "(${opt.label}) ${opt.text}",
                    fontSize = 10.sp,
                    modifier = Modifier.padding(start = 14.dp, top = 2.dp)
                )
            }
        }
    }
}
