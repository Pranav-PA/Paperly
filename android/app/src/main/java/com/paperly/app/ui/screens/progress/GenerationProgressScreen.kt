package com.paperly.app.ui.screens.progress

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.paperly.app.ui.theme.*

enum class GenerationStepStatus {
    DONE, IN_PROGRESS, PENDING
}

data class ProgressStep(
    val title: String,
    val status: GenerationStepStatus
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GenerationProgressScreen(
    currentStepIndex: Int = 4, // default validating
    paperTitle: String = "Your Paper"
) {
    val steps = listOf(
        ProgressStep("Requirements collected", if (currentStepIndex > 0) GenerationStepStatus.DONE else GenerationStepStatus.IN_PROGRESS),
        ProgressStep("Research completed", if (currentStepIndex > 1) GenerationStepStatus.DONE else if (currentStepIndex == 1) GenerationStepStatus.IN_PROGRESS else GenerationStepStatus.PENDING),
        ProgressStep("Sources analyzed", if (currentStepIndex > 2) GenerationStepStatus.DONE else if (currentStepIndex == 2) GenerationStepStatus.IN_PROGRESS else GenerationStepStatus.PENDING),
        ProgressStep("Questions generated", if (currentStepIndex > 3) GenerationStepStatus.DONE else if (currentStepIndex == 3) GenerationStepStatus.IN_PROGRESS else GenerationStepStatus.PENDING),
        ProgressStep("Validating questions & math", if (currentStepIndex > 4) GenerationStepStatus.DONE else if (currentStepIndex == 4) GenerationStepStatus.IN_PROGRESS else GenerationStepStatus.PENDING),
        ProgressStep("Creating document & layout", if (currentStepIndex > 5) GenerationStepStatus.DONE else if (currentStepIndex == 5) GenerationStepStatus.IN_PROGRESS else GenerationStepStatus.PENDING)
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Creating your paper", fontWeight = FontWeight.Bold, fontSize = 16.sp) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.White)
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Slate50)
                .padding(padding)
                .padding(24.dp),
            contentAlignment = Alignment.Center
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
                colors = CardDefaults.cardColors(containerColor = Color.White),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(
                    modifier = Modifier.padding(24.dp),
                    horizontalAlignment = Alignment.Start
                ) {
                    Text(
                        text = "Synthesizing $paperTitle",
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                        color = Slate900
                    )
                    Spacer(modifier = Modifier.height(16.dp))

                    steps.forEach { step ->
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(vertical = 8.dp)
                        ) {
                            when (step.status) {
                                GenerationStepStatus.DONE -> {
                                    Surface(
                                        shape = CircleShape,
                                        color = AccentGreen,
                                        modifier = Modifier.size(20.dp)
                                    ) {
                                        Icon(
                                            Icons.Default.Check,
                                            contentDescription = null,
                                            tint = Color.White,
                                            modifier = Modifier.padding(3.dp)
                                        )
                                    }
                                }
                                GenerationStepStatus.IN_PROGRESS -> {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(20.dp),
                                        strokeWidth = 2.5.dp,
                                        color = PrimaryBlue
                                    )
                                }
                                GenerationStepStatus.PENDING -> {
                                    Surface(
                                        shape = CircleShape,
                                        color = Slate200,
                                        modifier = Modifier.size(20.dp)
                                    ) {}
                                }
                            }
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = step.title,
                                fontSize = 13.sp,
                                fontWeight = if (step.status == GenerationStepStatus.IN_PROGRESS) FontWeight.Bold else FontWeight.Normal,
                                color = if (step.status == GenerationStepStatus.PENDING) TextSecondary else Slate900
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(24.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Please wait, rigorous validation underway...",
                            fontSize = 12.sp,
                            color = TextSecondary,
                            fontStyle = androidx.compose.ui.text.font.FontStyle.Italic
                        )
                    }
                }
            }
        }
    }
}
