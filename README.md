# Unifi Person Detector v2.0
This script is used to run YOLO object detection on video files recorded by the unifi camera and send notification if that happens.


Basic requirements:
```
Python 3.6+
Nvidia GPU 4GB+ (CUDA)
Darknet + Yolo (https://github.com/AlexeyAB/darknet)
Unifi Controller (v3.9+)
HomeAssistant (Notifications via Discord/iOS)
Webserver (HASS can access)

```

Create startscript with the following content (Ubuntu 16.04)
```
/etc/systemd/system/upd.service

[Unit]
Description=Unifi Person Detector
After=multi-user.target

[Service]
Type=simple
Environment=DISPLAY=:1
WorkingDirectory=/repo/unifi_person_detector
User=pi
ExecStart=/repo/unifi_person_detector/upd.py
StandardError=syslog

[Install]
WantedBy=multi-user.target
```

Controll upd with:
```
sudo systemctl enable upd.service   #Start upd service at startup
sudo systemctl start upd.service    #Start upd service
sudo systemctl stop upd.service     #Stop upd service
sudo systemctl status upd.service   #Show status of upd service
```

Install darknet with YOLO in /opt/darknet/ 
```
git clone https://github.com/AlexeyAB/darknet.git /opt/darknet
```
