# 🚀 Deployment: How to Use It
1. On a fresh Raspberry Pi, first download and run the installer.

```
curl -O https://raw.githubusercontent.com/philsmy/mm-yt-downloader-service/main/install_yt_downloader.sh
chmod +x install_yt_downloader.sh
```

2. Run the script with your Redis URL:

```
./install_yt_downloader.sh redis://username:password@host:port/db
```

You'll get the redis url from someone who knows!

# 🚀 After Deployment: How to Check Everything
1. Check the service status:

```
sudo systemctl status yt_downloader.service
```

Should say: active (running)

2. Check logs (real-time output):

```
sudo journalctl -u yt_downloader.service -f
```

3. If needed, restart the service:

```
sudo systemctl restart yt_downloader.service
```
