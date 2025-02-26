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