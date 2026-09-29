package com.paperly.app.ui.screens.export

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.paperly.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExportScreen(
    paperTitle: String,
    onBack: () -> Unit,
    onExport: (format: String, includeSolutions: Boolean, (Boolean, String?) -> Unit) -> Unit
) {
    val formats = listOf("PDF", "DOCX")
    var selectedFormat by remember { mutableStateOf(formats[0]) }
    var includeSolutions by remember { mutableStateOf(false) }
    var isExporting by remember { mutableStateOf(false) }
    var downloadResultPath by remember { mutableStateOf<String?>(null) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Export Paper", fontSize = 16.sp, fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.White)
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Slate50)
                .padding(padding)
                .padding(20.dp)
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(
                        text = paperTitle,
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                        color = Slate900
                    )
                    Spacer(modifier = Modifier.height(16.dp))

                    Text(
                        text = "Select Export Format",
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 13.sp,
                        color = Slate700
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    formats.forEach { format ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .selectable(
                                    selected = (format == selectedFormat),
                                    onClick = { selectedFormat = format }
                                )
                                .padding(vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            RadioButton(
                                selected = (format == selectedFormat),
                                onClick = { selectedFormat = format },
                                colors = RadioButtonDefaults.colors(selectedColor = PrimaryBlue)
                            )
                            Text(
                                text = if (format == "PDF") "PDF Document (Print-ready)" else "Microsoft Word DOCX (Editable)",
                                fontSize = 13.sp,
                                modifier = Modifier.padding(start = 8.dp)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(
                            checked = includeSolutions,
                            onCheckedChange = { includeSolutions = it },
                            colors = CheckboxDefaults.colors(checkedColor = PrimaryBlue)
                        )
                        Text(
                            text = "Include Answer Key & Detailed Solutions",
                            fontSize = 13.sp,
                            modifier = Modifier.padding(start = 6.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(24.dp))

                    Button(
                        onClick = {
                            isExporting = true
                            errorMessage = null
                            downloadResultPath = null
                            onExport(selectedFormat.lowercase(), includeSolutions) { success, result ->
                                isExporting = false
                                if (success) {
                                    downloadResultPath = result
                                } else {
                                    errorMessage = result ?: "Export failed"
                                }
                            }
                        },
                        enabled = !isExporting,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = PrimaryBlue)
                    ) {
                        if (isExporting) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White, strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Default.FileDownload, contentDescription = null)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("EXPORT ${selectedFormat}", fontWeight = FontWeight.Bold)
                        }
                    }

                    downloadResultPath?.let { path ->
                        Spacer(modifier = Modifier.height(16.dp))
                        Surface(
                            color = Color(0xFFDCFCE7),
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(Icons.Default.CheckCircle, contentDescription = null, tint = AccentGreen)
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = "Saved to: $path",
                                    fontSize = 12.sp,
                                    color = AccentGreen,
                                    fontWeight = FontWeight.Medium
                                )
                            }
                        }
                    }

                    errorMessage?.let { err ->
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(text = err, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                    }
                }
            }
        }
    }
}
