package com.paperly.app.ui.screens.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.paperly.app.data.local.entity.MessageEntity
import com.paperly.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    conversationTitle: String,
    messages: List<MessageEntity>,
    latestPaperId: String?,
    onBack: () -> Unit,
    onSendMessage: (String) -> Unit,
    onOpenEditor: (String) -> Unit,
    onUploadClick: () -> Unit
) {
    var inputText by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val coroutineScope = rememberCoroutineScope()

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            conversationTitle,
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            maxLines = 1,
                            color = Slate900
                        )
                        Text(
                            "Paperly AI Assistant",
                            fontSize = 11.sp,
                            color = TextSecondary
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    if (latestPaperId != null) {
                        IconButton(onClick = { onOpenEditor(latestPaperId) }) {
                            Icon(
                                Icons.Default.Description,
                                contentDescription = "Open Document",
                                tint = PrimaryBlue
                            )
                        }
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
        ) {
            // Paper Ready Notification Banner
            if (latestPaperId != null) {
                Surface(
                    color = Color(0xFFDCFCE7),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            "Question Paper generated!",
                            fontSize = 12.sp,
                            color = AccentGreen,
                            fontWeight = FontWeight.SemiBold
                        )
                        TextButton(onClick = { onOpenEditor(latestPaperId) }) {
                            Text("Open Editor", fontSize = 12.sp, color = AccentGreen, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            // Message History
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                items(messages) { msg ->
                    val isUser = msg.role == "user"
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
                    ) {
                        Surface(
                            shape = RoundedCornerShape(
                                topStart = 12.dp,
                                topEnd = 12.dp,
                                bottomStart = if (isUser) 12.dp else 2.dp,
                                bottomEnd = if (isUser) 2.dp else 12.dp
                            ),
                            color = if (isUser) PrimaryBlue else Color.White,
                            shadowElevation = 1.dp,
                            modifier = Modifier.widthIn(max = 300.dp)
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                if (!isUser) {
                                    Text(
                                        "Paperly",
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 11.sp,
                                        color = AccentTeal,
                                        modifier = Modifier.padding(bottom = 2.dp)
                                    )
                                }
                                Text(
                                    text = msg.content,
                                    fontSize = 13.sp,
                                    color = if (isUser) Color.White else Slate900,
                                    lineHeight = 18.sp
                                )
                            }
                        }
                    }
                }
            }

            // Input Bar with Attachment and Send buttons
            Surface(
                color = Color.White,
                shadowElevation = 4.dp
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(onClick = onUploadClick) {
                        Icon(
                            Icons.Default.AttachFile,
                            contentDescription = "Upload Source Material",
                            tint = Slate600
                        )
                    }

                    TextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        placeholder = { Text("Type your answer or instructions...", fontSize = 13.sp, color = TextSecondary) },
                        modifier = Modifier.weight(1f),
                        colors = TextFieldDefaults.colors(
                            focusedContainerColor = Color.Transparent,
                            unfocusedContainerColor = Color.Transparent,
                            focusedIndicatorColor = Color.Transparent,
                            unfocusedIndicatorColor = Color.Transparent
                        ),
                        maxLines = 4
                    )

                    IconButton(
                        onClick = {
                            if (inputText.isNotBlank()) {
                                val text = inputText
                                inputText = ""
                                onSendMessage(text)
                            }
                        },
                        enabled = inputText.isNotBlank()
                    ) {
                        Icon(
                            Icons.Default.Send,
                            contentDescription = "Send",
                            tint = if (inputText.isNotBlank()) PrimaryBlue else Slate600
                        )
                    }
                }
            }
        }
    }
}
