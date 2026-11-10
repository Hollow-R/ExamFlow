# ExamFlow

ExamFlow, öğretmenin yerel ağda sunucu olarak çalıştırdığı bir masaüstü sınav
uygulamasıdır. Mevcut sürüm; hesap/rol yönetimi, soru bankası, zamanlanmış
çoktan seçmeli ve klasik sınavlar, öğrenci gönderimleri, puanlama, sonuçlar ve
gönderim logları dahil vize kapsamını uygular.

## Gereksinimler

- Python 3.8
- `requirements.txt` dosyasındaki paketler
- Öğrenci bilgisayarlarının sunucu portuna erişebilmesi için Windows Firewall
  izni

PowerShell üzerinden bağımlılıkları kurun:

```powershell
py -3.8 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Öğretmen sunucusunu başlatma

Öğretmen bilgisayarında `desktop.py` dosyasını çalıştırın:

```powershell
.\.venv\Scripts\python.exe desktop.py
```

Sunucu varsayılan olarak `5000` portunda tüm ağ arayüzlerini dinler; debug
modunda çalışmaz. Başka bir port seçmek için:

```powershell
$env:EXAMFLOW_PORT = "5001"
.\.venv\Scripts\python.exe desktop.py
```

Bu porta Windows Firewall üzerinden gelen bağlantılara izin verin. Öğretmen,
varsayılanı `0000` olan davet koduyla `/auth/register` sayfasından kayıt olabilir.
Gerekirse sunucuyu başlatmadan önce `EXAMFLOW_TEACHER_REGISTRATION_CODE`
değişkeniyle kodu değiştirin. Öğrenciler de aynı sayfadan kayıt olabilir.

## Öğrenci masaüstünü bağlama

Her öğrenci bilgisayarında şu komutları çalıştırın:

```powershell
$env:EXAMFLOW_MODE = "client"
.\.venv\Scripts\python.exe desktop.py
```

Öğretmen bilgisayarının adresini girin; örneğin
`http://192.168.1.20:5000`. Uygulama sunucunun `/health` uç noktasını kontrol
eder ve adresi sonraki açılış için kaydeder. Bağlantı ekranını atlamak için
`EXAMFLOW_SERVER_URL` değişkeni de kullanılabilir.

Sunucu ve öğrenciler, bilgisayarlar arası bağlantıya izin veren aynı ağda
olmalıdır. Öğretmen bilgisayarının yerel IP adresini `ipconfig` komutuyla bulun.
`127.0.0.1` yalnızca öğretmen bilgisayarında kullanılabilir.

## Vize kapsamındaki davranışlar

- Öğretmenler çoktan seçmeli ve klasik soru ekleyebilir, düzenleyebilir,
  silebilir; soruları kategorilendirip zorluk belirleyebilir, zamanlanmış sınav
  oluşturabilir ve öğrenci sonuçlarını görüntüleyebilir.
- Sınavlar mevcut öğrencilere atanır. Daha sonra kaydolan bir öğrenci,
  başlangıç zamanı henüz geçmemiş sınavları alır.
- Gönderim kabul edilirken sınav başlangıç/bitiş zamanı sunucu tarafında
  denetlenir. Klasik cevaplar, baştaki/sondaki boşluklar ve harf büyüklüğü
  yok sayılarak tam metin eşleşmesiyle puanlanır; eş anlamlı ve kısmi cevap
  kabul edilmez.
- Başarılı gönderimler merkezi SQLite veritabanına kaydedilir ve
  `instance/submission_logs.jsonl` dosyasına yazılır. Öğretmen son gönderim
  loglarını uygulamada inceleyebilir.

Varsayılan `0000` davet kodu ve şifrelenmemiş HTTP bağlantısı yalnızca güvenilir
bir sınıf ağı içindir.

## Testler

Proje ortamında birim testlerini ve sözdizimi kontrolünü çalıştırın:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app.py desktop.py examflow tests
```

Firewall erişimi, giriş, sınav gönderimi ve öğretmen ekranında sonuç/log
görüntülenmesini en az bir ayrı öğrenci bilgisayarıyla ayrıca doğrulayın.
