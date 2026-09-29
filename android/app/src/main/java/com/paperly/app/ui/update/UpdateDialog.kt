package com.paperly.app.ui.update

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.SystemUpdate
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.viewModelScope
import com.paperly.app.BuildConfig
import com.paperly.app.data.PaperlyException
import com.paperly.app.data.UpdateInfo
import com.paperly.app.data.Updater
import kotlinx.coroutines.launch
import java.io.File

sealed interface UpdateState {
    data object Hidden : UpdateState
    data object Checking : UpdateState
    data object UpToDate : UpdateState
    data class Available(val info: UpdateInfo) : UpdateState
    data class Downloading(val info: UpdateInfo, val progress: Float) : UpdateState
    data class NeedsPermission(val info: UpdateInfo, val apk: File) : UpdateState
    data class Ready(val info: UpdateInfo, val apk: File) : UpdateState
    data class Failed(val info: UpdateInfo, val message: String) : UpdateState
}

class UpdateViewModel(private val updater: Updater) : ViewModel() {
    var state by mutableStateOf<UpdateState>(UpdateState.Hidden)
        private set

    private var checkedAutomatically = false

    /** Quiet check on app start: only shows something if an update exists. */
    fun autoCheck() {
        if (checkedAutomatically) return
        checkedAutomatically = true
        viewModelScope.launch { updater.check()?.let { state = UpdateState.Available(it) } }
    }

    /** Manual check from the menu: also reports "up to date". */
    fun manualCheck() {
        state = UpdateState.Checking
        viewModelScope.launch {
            state = updater.check()?.let { UpdateState.Available(it) } ?: UpdateState.UpToDate
        }
    }

    fun dismiss() {
        state = UpdateState.Hidden
    }

    fun download(info: UpdateInfo) {
        state = UpdateState.Downloading(info, 0f)
        viewModelScope.launch {
            state = try {
                val apk = updater.download(info) { p -> state = UpdateState.Downloading(info, p) }
                if (updater.canInstall()) UpdateState.Ready(info, apk) else UpdateState.NeedsPermission(info, apk)
            } catch (e: PaperlyException) {
                UpdateState.Failed(info, e.message ?: "Download failed.")
            }
        }
    }

    fun install(info: UpdateInfo, apk: File) {
        if (!updater.canInstall()) {
            state = UpdateState.NeedsPermission(info, apk)
            return
        }
        try {
            updater.install(apk)
            state = UpdateState.Ready(info, apk)
        } catch (e: Exception) {
            state = UpdateState.Failed(info, "Couldn't open the installer.")
        }
    }

    fun openPermissionSettings() = updater.openInstallPermissionSettings()

    /** Coming back from the "install unknown apps" screen: continue if it was allowed. */
    fun onResume() {
        (state as? UpdateState.NeedsPermission)?.let { s ->
            if (updater.canInstall()) install(s.info, s.apk)
        }
    }
}

@Composable
fun UpdateDialog(vm: UpdateViewModel) {
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { vm.onResume() }

    when (val s = vm.state) {
        UpdateState.Hidden -> Unit
        UpdateState.Checking -> AlertDialog(
            onDismissRequest = vm::dismiss,
            title = { Text("Checking for updates…") },
            text = { LinearProgressIndicator(Modifier.fillMaxWidth()) },
            confirmButton = {}
        )
        UpdateState.UpToDate -> AlertDialog(
            onDismissRequest = vm::dismiss,
            title = { Text("You're up to date") },
            text = { Text("Paperly ${BuildConfig.VERSION_NAME} is the latest version.") },
            confirmButton = { TextButton(onClick = vm::dismiss) { Text("OK") } }
        )
        is UpdateState.Available -> UpdateShell(
            info = s.info,
            body = { Notes(s.info) },
            confirm = { Button(onClick = { vm.download(s.info) }, shape = RoundedCornerShape(12.dp)) { Text("Update") } },
            dismiss = { TextButton(onClick = vm::dismiss) { Text("Later") } },
            onDismiss = vm::dismiss
        )
        is UpdateState.Downloading -> UpdateShell(
            info = s.info,
            body = {
                Text("Downloading… ${(s.progress * 100).toInt()}%")
                Spacer(Modifier.height(10.dp))
                LinearProgressIndicator(
                    progress = { s.progress },
                    modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(50))
                )
            },
            confirm = {},
            dismiss = {},
            onDismiss = {}
        )
        is UpdateState.NeedsPermission -> UpdateShell(
            info = s.info,
            body = {
                Text("One-time step: allow Paperly to install updates.")
                Spacer(Modifier.height(8.dp))
                Text(
                    "Tap Allow, switch on \"Allow from this source\", then come back. The update installs automatically.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            },
            confirm = { Button(onClick = vm::openPermissionSettings, shape = RoundedCornerShape(12.dp)) { Text("Allow") } },
            dismiss = { TextButton(onClick = vm::dismiss) { Text("Later") } },
            onDismiss = vm::dismiss
        )
        is UpdateState.Ready -> UpdateShell(
            info = s.info,
            body = { Text("Downloaded. Tap Install, then Install again on Android's screen.") },
            confirm = { Button(onClick = { vm.install(s.info, s.apk) }, shape = RoundedCornerShape(12.dp)) { Text("Install") } },
            dismiss = { TextButton(onClick = vm::dismiss) { Text("Later") } },
            onDismiss = vm::dismiss
        )
        is UpdateState.Failed -> UpdateShell(
            info = s.info,
            body = { Text(s.message, color = MaterialTheme.colorScheme.error) },
            confirm = { Button(onClick = { vm.download(s.info) }, shape = RoundedCornerShape(12.dp)) { Text("Try again") } },
            dismiss = { TextButton(onClick = vm::dismiss) { Text("Later") } },
            onDismiss = vm::dismiss
        )
    }
}

@Composable
private fun UpdateShell(
    info: UpdateInfo,
    body: @Composable ColumnScope.() -> Unit,
    confirm: @Composable () -> Unit,
    dismiss: @Composable () -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Rounded.SystemUpdate, null) },
        title = { Text("Update available: v${info.version}") },
        text = { Column(content = body) },
        confirmButton = confirm,
        dismissButton = dismiss
    )
}

@Composable
private fun Notes(info: UpdateInfo) {
    Column {
        Text(
            "You have v${BuildConfig.VERSION_NAME}.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        if (info.notes.isNotBlank()) {
            Spacer(Modifier.height(10.dp))
            Text(
                info.notes,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.heightIn(max = 280.dp).verticalScroll(rememberScrollState())
            )
        }
    }
}
