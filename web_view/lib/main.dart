import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

const String appTitle = 'Maareeye Expense Tracker';

const String baseUrl = String.fromEnvironment(
  'BASE_URL',
  defaultValue: 'https://maareye.vercel.app/login',
);

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const HomelandApp());
}

class HomelandApp extends StatelessWidget {
  const HomelandApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: appTitle,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: const Color(0xff0d6efd),
      ),
      home: const HomelandWebView(),
    );
  }
}

class HomelandWebView extends StatefulWidget {
  const HomelandWebView({super.key});

  @override
  State<HomelandWebView> createState() => _HomelandWebViewState();
}

class _HomelandWebViewState extends State<HomelandWebView> {
  late final WebViewController _controller;

  int _progress = 0;
  bool _hasError = false;

  @override
  void initState() {
    super.initState();

    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      // 🔥 FIX: Google Login wuxuu u baahan yahay User Agent casri ah
      ..setUserAgent('Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36')
      ..setBackgroundColor(Colors.white)
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (progress) {
            if (mounted) setState(() => _progress = progress);
          },
          onPageStarted: (url) {
            if (mounted) setState(() => _hasError = false);
          },
          onPageFinished: (url) {
            if (mounted) setState(() => _progress = 100);
          },
          onWebResourceError: (error) {
            if (mounted) setState(() => _hasError = true);
          },
          onNavigationRequest: (NavigationRequest request) {
            return NavigationDecision.navigate;
          },
        ),
      )
      ..loadRequest(Uri.parse(baseUrl));
  }

  Future<bool> _onBackPressed() async {
    if (await _controller.canGoBack()) {
      await _controller.goBack();
      return false;
    }
    return true;
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) async {
        if (didPop) return;
        final shouldPop = await _onBackPressed();
        if (shouldPop && context.mounted) {
          Navigator.of(context).maybePop();
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text(appTitle),
          centerTitle: true,
          actions: [
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: () => _controller.reload(),
            ),
          ],
        ),
        body: SafeArea(
          child: Stack(
            children: [
              WebViewWidget(controller: _controller),
              if (_progress < 100)
                LinearProgressIndicator(value: _progress / 100, minHeight: 3),
              if (_hasError)
                _ConnectionError(onRetry: () => _controller.reload()),
            ],
          ),
        ),
      ),
    );
  }
}

class _ConnectionError extends StatelessWidget {
  final VoidCallback onRetry;
  const _ConnectionError({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.white,
      alignment: Alignment.center,
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, size: 70, color: Colors.red),
          const SizedBox(height: 20),
          const Text('Khalad baa dhacay', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Isku day mar kale'),
          ),
        ],
      ),
    );
  }
}