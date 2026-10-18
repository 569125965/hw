package com.asharelab.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.asharelab.app.ui.research.ResearchScreen
import com.asharelab.app.ui.search.SearchScreen
import com.asharelab.app.ui.theme.AShareTheme
import com.asharelab.app.ui.theme.Bg1

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            AShareTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = Bg1) {
                    AShareNav()
                }
            }
        }
    }
}

@Composable
private fun AShareNav() {
    val nav = rememberNavController()
    NavHost(navController = nav, startDestination = "search") {
        composable("search") {
            SearchScreen(onOpen = { code -> nav.navigate("research/$code") })
        }
        composable(
            route = "research/{code}",
            arguments = listOf(navArgument("code") { type = NavType.StringType })
        ) { entry ->
            val code = entry.arguments?.getString("code").orEmpty()
            ResearchScreen(
                code = code,
                onBack = { nav.popBackStack() },
                onOpenPeer = { peer ->
                    nav.navigate("research/$peer") {
                        launchSingleTop = true
                    }
                }
            )
        }
    }
}
