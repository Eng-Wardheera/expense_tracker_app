import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

const String appTitle = 'Homeland Real Estate';

// 🔥 Use correct base URL (NO trailing slash recommended)
const String baseUrl = String.fromEnvironment(
  'BASE_URL',
  defaultValue: 'http://10.238.211.90:7000',
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
      ..setBackgroundColor(Colors.white)
      // 🔥 IMPORTANT: allow all navigation (fix detail page issue)
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (progress) {
            if (mounted) {
              setState(() {
                _progress = progress;
              });
            }
          },

          onPageStarted: (url) {
            if (mounted) {
              setState(() {
                _hasError = false;
                _progress = 0;
              });
            }
          },

          onPageFinished: (url) {
            if (mounted) {
              setState(() {
                _progress = 100;
              });
            }
          },

          onWebResourceError: (error) {
            if (mounted) {
              setState(() {
                _hasError = true;
              });
            }
          },

          // 🔥 CRITICAL FIX: allow ALL links (property detail included)
          onNavigationRequest: (NavigationRequest request) {
            return NavigationDecision.navigate;
          },
        ),
      )
      // 🔥 LOAD MAIN PAGE
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
          title: const Text("Homeland Real Estate"),
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

              // 🔵 Loading bar
              if (_progress < 100)
                LinearProgressIndicator(value: _progress / 100, minHeight: 3),

              // 🔴 Error screen
              if (_hasError)
                _ConnectionError(
                  onRetry: () {
                    _controller.reload();
                  },
                ),
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
          const Icon(Icons.home_work_outlined, size: 70, color: Colors.blue),

          const SizedBox(height: 20),

          const Text(
            'Unable to connect to Homeland Real Estate System',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),

          const SizedBox(height: 10),

          const Text(
            'Check Flask server (host=0.0.0.0, port=7000) and network access.',
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 25),

          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry Connection'),
          ),
        ],
      ),
    );
  }
}
