import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

const String API_URL = 'https://messenger-clone-zbef.onrender.com';
void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Messenger',
      theme: ThemeData(
        brightness: Brightness.dark,
        colorSchemeSeed: Colors.blue,
        useMaterial3: true,
      ),
      home: const LoginPage(),
    );
  }
}

// ================= API =================

class Api {
  static Future<Map<String, dynamic>> post(
    String path,
    Map<String, dynamic> data,
  ) async {
    final response = await http.post(
      Uri.parse('$API_URL$path'),
      headers: {
        'Content-Type': 'application/json',
      },
      body: jsonEncode(data),
    );

    if (response.body.isEmpty) {
      return {
        'ok': false,
        'message': 'Server javob bermadi',
      };
    }

    final result = jsonDecode(response.body);

    if (result is Map<String, dynamic>) {
      if (result['success'] == true && result['ok'] == null) {
        result['ok'] = true;
      }

      if (result['detail'] != null &&
          result['message'] == null) {
        result['message'] = result['detail'];
      }

      return result;
    }

    return {
      'ok': false,
      'message': 'Server javobi noto‘g‘ri',
    };
  }

  static Future<Map<String, dynamic>> get(
    String path,
  ) async {
    final response = await http.get(
      Uri.parse('$API_URL$path'),
    );

    if (response.body.isEmpty) {
      return {
        'ok': false,
        'message': 'Server javob bermadi',
      };
    }

    final result = jsonDecode(response.body);

    if (result is Map<String, dynamic>) {
      if (result['success'] == true && result['ok'] == null) {
        result['ok'] = true;
      }

      if (result['detail'] != null &&
          result['message'] == null) {
        result['message'] = result['detail'];
      }

      return result;
    }

    return {
      'ok': false,
      'message': 'Server javobi noto‘g‘ri',
    };
  }
}

// ================= LOGIN =================

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final phone = TextEditingController();
  final password = TextEditingController();

  bool loading = false;

  Future<void> login() async {
    if (phone.text.trim().isEmpty ||
        password.text.isEmpty) {
      showMsg(
        'Telefon raqam va parolni kiriting',
      );
      return;
    }

    setState(() => loading = true);

    try {
      final result = await Api.post('/login', {
        'phone': phone.text.trim(),
        'password': password.text,
      });

      if (!mounted) return;

      if (result['ok'] == true) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => HomePage(
              user: Map<String, dynamic>.from(
                result['user'] ?? {},
              ),
            ),
          ),
        );
      } else {
        showMsg(
          result['message'] ?? 'Login xatosi',
        );
      }
    } catch (e) {
      if (mounted) {
        showMsg(
          'Serverga ulanib bo‘lmadi',
        );
      }
    }

    if (mounted) {
      setState(() => loading = false);
    }
  }

  void showMsg(String text) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(text)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                const Icon(
                  Icons.forum_rounded,
                  size: 90,
                  color: Colors.blue,
                ),

                const SizedBox(height: 20),

                const Text(
                  'Messenger',
                  style: TextStyle(
                    fontSize: 34,
                    fontWeight: FontWeight.bold,
                  ),
                ),

                const SizedBox(height: 35),

                TextField(
                  controller: phone,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(
                    labelText: 'Telefon raqam',
                    prefixIcon: Icon(Icons.phone),
                    border: OutlineInputBorder(),
                  ),
                ),

                const SizedBox(height: 15),

                TextField(
                  controller: password,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Parol',
                    prefixIcon: Icon(Icons.lock),
                    border: OutlineInputBorder(),
                  ),
                ),

                const SizedBox(height: 20),

                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: FilledButton(
                    onPressed: loading ? null : login,
                    child: loading
                        ? const CircularProgressIndicator()
                        : const Text('Kirish'),
                  ),
                ),

                const SizedBox(height: 12),

                TextButton(
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) =>
                            const RegisterPage(),
                      ),
                    );
                  },
                  child: const Text(
                    'Yangi akkaunt yaratish',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ================= REGISTER =================

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() =>
      _RegisterPageState();
}

class _RegisterPageState
    extends State<RegisterPage> {
  final phone = TextEditingController();
  final name = TextEditingController();
  final password = TextEditingController();
  final referral = TextEditingController();

  bool loading = false;

  Future<void> register() async {
    if (phone.text.trim().isEmpty ||
        name.text.trim().isEmpty ||
        password.text.length < 6) {
      showMsg(
        'Ma’lumotlarni to‘g‘ri kiriting',
      );
      return;
    }

    setState(() => loading = true);

    try {
      final result = await Api.post('/register', {
        'phone': phone.text.trim(),
        'name': name.text.trim(),
        'password': password.text,
        'referral': referral.text.trim(),
      });

      if (!mounted) return;

      if (result['ok'] == true) {
        showMsg('Akkaunt yaratildi');
        Navigator.pop(context);
      } else {
        showMsg(
          result['message'] ??
              'Ro‘yxatdan o‘tishda xato',
        );
      }
    } catch (e) {
      if (mounted) {
        showMsg(
          'Serverga ulanib bo‘lmadi',
        );
      }
    }

    if (mounted) {
      setState(() => loading = false);
    }
  }

  void showMsg(String text) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(text)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Akkaunt yaratish',
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            TextField(
              controller: name,
              decoration: const InputDecoration(
                labelText: 'Ism',
                prefixIcon: Icon(Icons.person),
                border: OutlineInputBorder(),
              ),
            ),

            const SizedBox(height: 14),

            TextField(
              controller: phone,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(
                labelText: 'Telefon raqam',
                prefixIcon: Icon(Icons.phone),
                border: OutlineInputBorder(),
              ),
            ),

            const SizedBox(height: 14),

            TextField(
              controller: password,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Parol',
                prefixIcon: Icon(Icons.lock),
                border: OutlineInputBorder(),
              ),
            ),

            const SizedBox(height: 14),

            TextField(
              controller: referral,
              decoration: const InputDecoration(
                labelText:
                    'Referral kod (ixtiyoriy)',
                prefixIcon:
                    Icon(Icons.group_add),
                border: OutlineInputBorder(),
              ),
            ),

            const SizedBox(height: 22),

            SizedBox(
              width: double.infinity,
              height: 52,
              child: FilledButton(
                onPressed:
                    loading ? null : register,
                child: loading
                    ? const CircularProgressIndicator()
                    : const Text(
                        'Ro‘yxatdan o‘tish',
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ================= HOME =================

class HomePage extends StatefulWidget {
  final Map<String, dynamic> user;

  const HomePage({
    super.key,
    required this.user,
  });

  @override
  State<HomePage> createState() =>
      _HomePageState();
}

class _HomePageState
    extends State<HomePage> {
  int index = 0;

  @override
  Widget build(BuildContext context) {
    final pages = [
      ChatPage(),
      GiftsPage(user: widget.user),
      WalletPage(user: widget.user),
      ProfilePage(user: widget.user),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Messenger'),
      ),

      body: pages[index],

      bottomNavigationBar:
          NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) {
          setState(() => index = value);
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.chat),
            label: 'Chatlar',
          ),
          NavigationDestination(
            icon: Icon(Icons.card_giftcard),
            label: 'Giftlar',
          ),
          NavigationDestination(
            icon: Icon(Icons.star),
            label: 'Stars',
          ),
          NavigationDestination(
            icon: Icon(Icons.person),
            label: 'Profil',
          ),
        ],
      ),
    );
  }
}

// ================= CHATS =================

class ChatPage extends StatelessWidget {
  ChatPage({super.key});

  final TextEditingController search =
      TextEditingController();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(15),
          child: TextField(
            controller: search,
            decoration: const InputDecoration(
              hintText:
                  'Chatlarni qidirish',
              prefixIcon:
                  Icon(Icons.search),
              border:
                  OutlineInputBorder(),
            ),
          ),
        ),

        const Expanded(
          child: Center(
            child: Text(
              'Hozircha chatlar yo‘q',
              style: TextStyle(
                fontSize: 18,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

// ================= GIFTS =================

class GiftsPage extends StatelessWidget {
  final Map<String, dynamic> user;

  const GiftsPage({
    super.key,
    required this.user,
  });

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<
        Map<String, dynamic>>(
      future: Api.get('/gifts'),
      builder:
          (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(
            child:
                CircularProgressIndicator(),
          );
        }

        final result =
            snapshot.data!;

        if (result['ok'] != true) {
          return Center(
            child: Text(
              result['message'] ??
                  'Giftlarni yuklab bo‘lmadi',
            ),
          );
        }

        final gifts =
            result['gifts'] ?? [];

        if (gifts.isEmpty) {
          return const Center(
            child: Text(
              'Giftlar hali mavjud emas',
            ),
          );
        }

        return GridView.builder(
          padding:
              const EdgeInsets.all(15),
          gridDelegate:
              const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
          ),
          itemCount: gifts.length,
          itemBuilder:
              (context, i) {
            final gift =
                gifts[i];

            return Card(
              child: InkWell(
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          GiftDetailPage(
                        gift: Map<
                            String,
                            dynamic>.from(
                          gift,
                        ),
                        user: user,
                      ),
                    ),
                  );
                },
                child: Column(
                  mainAxisAlignment:
                      MainAxisAlignment
                          .center,
                  children: [
                    const Icon(
                      Icons.card_giftcard,
                      size: 55,
                      color: Colors.pink,
                    ),

                    const SizedBox(
                      height: 8,
                    ),

                    Text(
                      gift['name'] ??
                          'Gift',
                      style:
                          const TextStyle(
                        fontWeight:
                            FontWeight.bold,
                      ),
                    ),

                    const SizedBox(
                      height: 5,
                    ),

                    Text(
                      '${gift['price']} ⭐',
                      style:
                          const TextStyle(
                        color:
                            Colors.amber,
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }
}

// ================= GIFT DETAIL =================

class GiftDetailPage
    extends StatelessWidget {
  final Map<String, dynamic> gift;
  final Map<String, dynamic> user;

  const GiftDetailPage({
    super.key,
    required this.gift,
    required this.user,
  });

  Future<void> buy(
    BuildContext context,
  ) async {
    final result =
        await Api.post(
      '/gift/buy',
      {
        'userId': user['id'],
        'giftId': gift['id'],
      },
    );

    if (!context.mounted) return;

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(
      SnackBar(
        content: Text(
          result['message'] ??
              'Amal bajarildi',
        ),
      ),
    );
  }

  @override
  Widget build(
    BuildContext context,
  ) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          gift['name'] ?? 'Gift',
        ),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment:
              MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.card_giftcard,
              size: 130,
              color: Colors.pink,
            ),

            const SizedBox(
              height: 20,
            ),

            Text(
              gift['name'] ??
                  'Gift',
              style:
                  const TextStyle(
                fontSize: 28,
                fontWeight:
                    FontWeight.bold,
              ),
            ),

            const SizedBox(
              height: 10,
            ),

            Text(
              '${gift['price']} ⭐',
              style:
                  const TextStyle(
                fontSize: 22,
                color:
                    Colors.amber,
              ),
            ),

            const SizedBox(
              height: 30,
            ),

            FilledButton.icon(
              onPressed: () =>
                  buy(context),
              icon: const Icon(
                Icons.shopping_cart,
              ),
              label: const Text(
                'Sotib olish',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ================= WALLET =================

class WalletPage
    extends StatelessWidget {
  final Map<String, dynamic> user;

  const WalletPage({
    super.key,
    required this.user,
  });

  @override
  Widget build(
    BuildContext context,
  ) {
    return FutureBuilder<
        Map<String, dynamic>>(
      future: Api.get(
        '/users/${user['id']}/balance',
      ),
      builder:
          (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(
            child:
                CircularProgressIndicator(),
          );
        }

        final result =
            snapshot.data!;

        return Center(
          child: Column(
            mainAxisAlignment:
                MainAxisAlignment
                    .center,
            children: [
              const Icon(
                Icons.star,
                color: Colors.amber,
                size: 90,
              ),

              const SizedBox(
                height: 15,
              ),

              const Text(
                'Stars balans',
                style:
                    TextStyle(
                  fontSize: 20,
                ),
              ),

              const SizedBox(
                height: 8,
              ),

              Text(
                '${result['stars'] ?? 0} ⭐',
                style:
                    const TextStyle(
                  fontSize: 35,
                  fontWeight:
                      FontWeight.bold,
                  color:
                      Colors.amber,
                ),
              ),

              const SizedBox(
                height: 30,
              ),

              FilledButton(
                onPressed: () {},
                child:
                    const Text(
                  'Stars sotib olish',
                ),
              ),

              const SizedBox(
                height: 12,
              ),

              FilledButton(
                onPressed: () {},
                child:
                    const Text(
                  'Premium',
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ================= PROFILE =================

class ProfilePage
    extends StatelessWidget {
  final Map<String, dynamic> user;

  const ProfilePage({
    super.key,
    required this.user,
  });

  @override
  Widget build(
    BuildContext context,
  ) {
    final isOwner =
                user['isOwner'] == true;

    return ListView(
      padding: const EdgeInsets.all(18),
      children: [
        const CircleAvatar(
          radius: 50,
          child: Icon(
            Icons.person,
            size: 55,
          ),
        ),

        const SizedBox(height: 15),

        Center(
          child: Text(
            user['name'] ?? 'Foydalanuvchi',
            style: const TextStyle(
              fontSize: 25,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),

        const SizedBox(height: 5),

        Center(
          child: Text(
            user['phone'] ?? '',
            style: const TextStyle(
              color: Colors.grey,
            ),
          ),
        ),

        const SizedBox(height: 25),

        ListTile(
          leading: const Icon(
            Icons.card_giftcard,
          ),
          title: const Text(
            'Mening giftlarim',
          ),
          trailing: const Icon(
            Icons.chevron_right,
          ),
          onTap: () {},
        ),

        ListTile(
          leading: const Icon(
            Icons.group,
          ),
          title: const Text(
            'Referral',
          ),
          trailing: const Icon(
            Icons.chevron_right,
          ),
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => ReferralPage(
                  user: user,
                ),
              ),
            );
          },
        ),

        ListTile(
          leading: const Icon(
            Icons.workspace_premium,
          ),
          title: const Text(
            'Premium',
          ),
          trailing: const Icon(
            Icons.chevron_right,
          ),
          onTap: () {},
        ),

        if (isOwner)
          Card(
            color: Colors.blue.withOpacity(.15),
            child: ListTile(
              leading: const Icon(
                Icons.admin_panel_settings,
                color: Colors.blue,
              ),
              title: const Text(
                'Owner / Admin panel',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                ),
              ),
              trailing: const Icon(
                Icons.chevron_right,
              ),
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => AdminPage(
                      user: user,
                    ),
                  ),
                );
              },
            ),
          ),
      ],
    );
  }
}

// ================= REFERRAL =================

class ReferralPage extends StatefulWidget {
  final Map<String, dynamic> user;

  const ReferralPage({
    super.key,
    required this.user,
  });

  @override
  State<ReferralPage> createState() =>
      _ReferralPageState();
}

class _ReferralPageState
    extends State<ReferralPage> {
  late Future<Map<String, dynamic>> referralFuture;

  @override
  void initState() {
    super.initState();
    referralFuture = Api.get(
      '/users/${widget.user['id']}/referral',
    );
  }

  void refresh() {
    setState(() {
      referralFuture = Api.get(
        '/users/${widget.user['id']}/referral',
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Referral'),
      ),
      body: FutureBuilder<Map<String, dynamic>>(
        future: referralFuture,
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return const Center(
              child: CircularProgressIndicator(),
            );
          }

          final data = snapshot.data!;

          if (data['ok'] != true) {
            return Center(
              child: Text(
                data['message'] ??
                    'Referral ma’lumotlarini yuklab bo‘lmadi',
              ),
            );
          }

          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                const SizedBox(height: 20),

                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment:
                          CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Taklif havolangiz',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight:
                                FontWeight.bold,
                          ),
                        ),

                        const SizedBox(height: 12),

                        SelectableText(
                          data['referral_link']
                                  ?.toString() ??
                              '',
                          style: const TextStyle(
                            fontSize: 16,
                            color: Colors.blue,
                          ),
                        ),

                        const SizedBox(height: 15),

                        SizedBox(
                          width: double.infinity,
                          child:
                              ElevatedButton.icon(
                            onPressed: () {
                              final link =
                                  data['referral_link']
                                          ?.toString() ??
                                      '';

                              if (link.isEmpty) return;

                              Clipboard.setData(
                                ClipboardData(
                                  text: link,
                                ),
                              );

                              ScaffoldMessenger.of(
                                context,
                              ).showSnackBar(
                                const SnackBar(
                                  content: Text(
                                    'Havola nusxalandi',
                                  ),
                                ),
                              );
                            },
                            icon: const Icon(
                              Icons.copy,
                            ),
                            label: const Text(
                              'Havolani nusxalash',
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 20),

                Card(
                  child: ListTile(
                    leading: const Icon(
                      Icons.people,
                      color: Colors.blue,
                      size: 32,
                    ),
                    title: const Text(
                      'Taklif qilinganlar',
                      style: TextStyle(
                        fontWeight:
                            FontWeight.bold,
                      ),
                    ),
                    subtitle: Text(
                      '${data['referrals'] ?? 0} ta foydalanuvchi',
                    ),
                  ),
                ),

                const SizedBox(height: 20),

                Card(
                  child: ListTile(
                    leading: const Icon(
                      Icons.star,
                      color: Colors.amber,
                      size: 32,
                    ),
                    title: const Text(
                      'Referral mukofoti',
                      style: TextStyle(
                        fontWeight:
                            FontWeight.bold,
                      ),
                    ),
                    subtitle: Text(
                      '${data['earned_stars'] ?? 0} ⭐ Stars',
                    ),
                  ),
                ),

                const SizedBox(height: 30),

                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: refresh,
                    child: const Text(
                      'Yangilash',
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

// ================= ADMIN =================

class AdminPage extends StatelessWidget {
  final Map<String, dynamic> user;

  const AdminPage({
    super.key,
    required this.user,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Owner / Admin panel',
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(18),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(
                Icons.people,
                color: Colors.blue,
              ),
              title: const Text(
                'Foydalanuvchilar',
              ),
              subtitle: const Text(
                'Foydalanuvchilarni boshqarish',
              ),
              trailing: const Icon(
                Icons.chevron_right,
              ),
              onTap: () {},
            ),
          ),

          Card(
            child: ListTile(
              leading: const Icon(
                Icons.card_giftcard,
                color: Colors.pink,
              ),
              title: const Text(
                'Giftlar',
              ),
              subtitle: const Text(
                'Giftlarni boshqarish',
              ),
              trailing: const Icon(
                Icons.chevron_right,
              ),
              onTap: () {},
            ),
          ),

          Card(
            child: ListTile(
              leading: const Icon(
                Icons.star,
                color: Colors.amber,
              ),
              title: const Text(
                'Stars',
              ),
              subtitle: const Text(
                'Stars balansini boshqarish',
              ),
              trailing: const Icon(
                Icons.chevron_right,
              ),
              onTap: () {},
            ),
          ),

          Card(
            child: ListTile(
              leading: const Icon(
                Icons.settings,
              ),
              title: const Text(
                'Sozlamalar',
              ),
              trailing: const Icon(
                Icons.chevron_right,
              ),
              onTap: () {},
            ),
          ),
        ],
      ),
    );
  }
}
