package com.paperly.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import com.paperly.app.ui.navigation.PaperlyNavGraph
import com.paperly.app.ui.theme.PaperlyTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val app = application as PaperlyApp

        setContent {
            PaperlyTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val navController = rememberNavController()
                    PaperlyNavGraph(
                        navController = navController,
                        authRepo = app.authRepository,
                        convRepo = app.conversationRepository,
                        paperRepo = app.paperRepository
                    )
                }
            }
        }
    }
}
