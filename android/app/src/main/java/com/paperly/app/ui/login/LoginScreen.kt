package com.paperly.app.ui.login

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.paperly.app.data.PaperlyException
import com.paperly.app.data.PaperlyRepository
import com.paperly.app.data.SessionStore
import com.paperly.app.ui.components.BrandMark
import com.paperly.app.ui.components.ErrorBanner
import com.paperly.app.ui.components.GradientButton
import com.paperly.app.ui.theme.LocalPaperlyExtras
import com.paperly.app.ui.theme.Success
import com.paperly.app.ui.theme.Warning
import kotlinx.coroutines.launch

sealed interface ServerStatus {
    data object Unknown : ServerStatus
    data object Checking : ServerStatus
    data class Online(val aiMode: String?, val model: String?) : ServerStatus
    data class Offline(val message: String) : ServerStatus
}

class LoginViewModel(private val repo: PaperlyRepository, private val store: SessionStore) : ViewModel() {
    var serverUrl by mutableStateOf(store.current.serverUrl.trimEnd('/'))
    var username by mutableStateOf(store.current.username.orEmpty())
    var password by mutableStateOf("")
    var loading by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
    var serverStatus by mutableStateOf<ServerStatus>(ServerStatus.Unknown)
        private set

    fun testConnection() {
        if (serverUrl.isBlank()) {
            serverStatus = ServerStatus.Offline("Enter the URL shown in Termux first.")
            return
        }
        store.setServerUrl(serverUrl)
        serverStatus = ServerStatus.Checking
        viewModelScope.launch {
            serverStatus = try {
                val health = repo.checkServer(serverUrl)
                ServerStatus.Online(health.aiMode, health.model)
            } catch (e: PaperlyException) {
                ServerStatus.Offline(e.message ?: "Not reachable")
            }
        }
    }

    fun login() {
        if (serverUrl.isBlank()) {
            error = "Add your server URL under Server settings."
            return
        }
        store.setServerUrl(serverUrl)
        loading = true
        error = null
        viewModelScope.launch {
            try {
                repo.login(username, password)
            } catch (e: PaperlyException) {
                error = e.message
            } finally {
                loading = false
            }
        }
    }
}

@Composable
fun LoginScreen(vm: LoginViewModel) {
    val extras = LocalPaperlyExtras.current
    val focus = LocalFocusManager.current
    var showPassword by remember { mutableStateOf(false) }
    var serverExpanded by remember { mutableStateOf(vm.serverUrl.isBlank()) }

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        // Hero gradient behind the top of the card
        Box(
            Modifier
                .fillMaxWidth()
                .height(340.dp)
                .clip(RoundedCornerShape(bottomStart = 40.dp, bottomEnd = 40.dp))
                .background(extras.heroGradient)
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 22.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(Modifier.height(48.dp))
            Box(Modifier.clip(RoundedCornerShape(22.dp)).background(Color.White.copy(alpha = 0.18f)).padding(10.dp)) {
                BrandMark(size = 56.dp)
            }
            Spacer(Modifier.height(18.dp))
            Text("Paperly", style = MaterialTheme.typography.displaySmall, color = Color.White)
            Text(
                "AI question papers, crafted in minutes",
                style = MaterialTheme.typography.bodyLarge,
                color = Color.White.copy(alpha = 0.85f)
            )
            Spacer(Modifier.height(32.dp))

            Surface(
                shape = RoundedCornerShape(28.dp),
                color = MaterialTheme.colorScheme.surface,
                shadowElevation = 6.dp,
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(Modifier.animateContentSize().padding(22.dp)) {
                    Text("Welcome back", style = MaterialTheme.typography.headlineSmall)
                    Text(
                        "Sign in with the account your admin gave you.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.height(20.dp))

                    vm.error?.let {
                        ErrorBanner(it)
                        Spacer(Modifier.height(14.dp))
                    }

                    OutlinedTextField(
                        value = vm.username,
                        onValueChange = { vm.username = it; vm.error = null },
                        label = { Text("Username") },
                        leadingIcon = { Icon(Icons.Rounded.Person, contentDescription = null) },
                        singleLine = true,
                        shape = RoundedCornerShape(16.dp),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii, imeAction = ImeAction.Next),
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = vm.password,
                        onValueChange = { vm.password = it; vm.error = null },
                        label = { Text("Password") },
                        leadingIcon = { Icon(Icons.Rounded.Lock, contentDescription = null) },
                        trailingIcon = {
                            IconButton(onClick = { showPassword = !showPassword }) {
                                Icon(
                                    if (showPassword) Icons.Rounded.VisibilityOff else Icons.Rounded.Visibility,
                                    contentDescription = if (showPassword) "Hide password" else "Show password"
                                )
                            }
                        },
                        visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                        singleLine = true,
                        shape = RoundedCornerShape(16.dp),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = { focus.clearFocus(); vm.login() }),
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(Modifier.height(20.dp))
                    GradientButton(
                        text = "Sign in",
                        onClick = { focus.clearFocus(); vm.login() },
                        enabled = vm.username.isNotBlank() && vm.password.isNotBlank(),
                        loading = vm.loading,
                        icon = Icons.Rounded.ArrowForward,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }

            Spacer(Modifier.height(16.dp))

            // Server settings
            Surface(
                shape = RoundedCornerShape(22.dp),
                color = MaterialTheme.colorScheme.surface,
                tonalElevation = 1.dp,
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(Modifier.animateContentSize()) {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clickable { serverExpanded = !serverExpanded }
                            .padding(horizontal = 18.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Rounded.Dns, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text("Server settings", style = MaterialTheme.typography.titleSmall)
                            Text(
                                vm.serverUrl.ifBlank { "Not set" },
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1
                            )
                        }
                        Icon(
                            if (serverExpanded) Icons.Rounded.ExpandLess else Icons.Rounded.ExpandMore,
                            contentDescription = null
                        )
                    }
                    AnimatedVisibility(serverExpanded) {
                        Column(Modifier.padding(start = 18.dp, end = 18.dp, bottom = 18.dp)) {
                            OutlinedTextField(
                                value = vm.serverUrl,
                                onValueChange = { vm.serverUrl = it.trim() },
                                label = { Text("Server URL") },
                                placeholder = { Text("https://xxxx.trycloudflare.com") },
                                singleLine = true,
                                shape = RoundedCornerShape(16.dp),
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done),
                                keyboardActions = KeyboardActions(onDone = { focus.clearFocus(); vm.testConnection() }),
                                modifier = Modifier.fillMaxWidth()
                            )
                            Text(
                                "Shown in Termux after running start_termux.sh",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(top = 6.dp, start = 4.dp)
                            )
                            Spacer(Modifier.height(12.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                FilledTonalButton(onClick = { focus.clearFocus(); vm.testConnection() }, shape = RoundedCornerShape(14.dp)) {
                                    Icon(Icons.Rounded.Wifi, contentDescription = null, modifier = Modifier.size(18.dp))
                                    Spacer(Modifier.width(6.dp))
                                    Text("Test connection")
                                }
                                Spacer(Modifier.width(12.dp))
                                ServerStatusLabel(vm.serverStatus, Modifier.weight(1f))
                            }
                        }
                    }
                }
            }
            Spacer(Modifier.height(28.dp))
        }
    }
}

@Composable
private fun ServerStatusLabel(status: ServerStatus, modifier: Modifier = Modifier) {
    when (status) {
        ServerStatus.Unknown -> Spacer(modifier)
        ServerStatus.Checking -> Row(modifier, verticalAlignment = Alignment.CenterVertically) {
            CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(8.dp))
            Text("Checking…", style = MaterialTheme.typography.bodySmall)
        }
        is ServerStatus.Online -> {
            val ai = status.aiMode == "gemini"
            Text(
                if (ai) "Connected · ${status.model}" else "Connected · demo mode (no Gemini key)",
                style = MaterialTheme.typography.labelMedium,
                color = if (ai) Success else Warning,
                modifier = modifier
            )
        }
        is ServerStatus.Offline -> Text(
            status.message,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.error,
            modifier = modifier
        )
    }
}
