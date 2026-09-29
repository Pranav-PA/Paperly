# Keep class/method names so crash reports are readable (shrinking still applies).
-dontobfuscate

# Gson maps JSON onto these classes by field name via reflection.
-keep class com.paperly.app.data.model.** { *; }
-keepattributes Signature, *Annotation*, InnerClasses, EnclosingMethod
# Retrofit service interface (suspend functions need generic signatures).
-keep,allowobfuscation interface com.paperly.app.data.remote.PaperlyApi
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation
-keep,allowobfuscation,allowshrinking class retrofit2.Response
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
