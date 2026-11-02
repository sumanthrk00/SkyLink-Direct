import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skylink_direct/main.dart';

void main() {
  testWidgets('authentication screen identifies simulation-only service', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: AuthScreen(api: Api(), onLogin: (_) {}),
    ));

    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Simulation only · No real satellite connection'), findsOneWidget);
  });
}
