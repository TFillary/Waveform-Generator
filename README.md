# An Abitrary Waveform Generator for the Raspberry Pi Pico
Based on AWG by Rolf Oldeman, 7/2/2021. CC BY-NC-SA 4.0 licence.
This implimentation was modified to be simpler, using a few resistors, a couple of rotary encoder switches and a small OLED display for control.
The signal sample buffer is 100 samples deep so with the Pico hardware running at 125Mhz the maximum frequency output is approx 1.25Mhz. Using the right hand rotary switch changes the frequency multiplyer can be changed to increase/decrease the frequency in x1Hz, x10hz, x100Khz, x1Khz, x10Khz, x100Khz, x1Mhz. Pushing the switch locks it and rotating it again changes the frequency.  The left hand switch changes the waveform type and when everything is as desired pushing the left hand switch sets the output to match.
![IMG_0112](https://user-images.githubusercontent.com/30411837/177044577-b5841576-f6e5-4186-bcad-19bc4da7d945.jpg)
The AWG output was tested with the Scoppy software in another Rpi Pico and an Android phone.  The following photos show the different waveforms available.
![IMG_0105](https://user-images.githubusercontent.com/30411837/177044587-f6444e38-bb42-4135-8d2b-9f0b0e8574b1.jpg)
![IMG_0106](https://user-images.githubusercontent.com/30411837/177044592-61009d1b-d67e-42c7-8887-71f52fe8a61c.jpg)
![IMG_0107](https://user-images.githubusercontent.com/30411837/177044594-48dee2d0-a3fc-47d0-9fd2-d9412d635f58.jpg)
![IMG_0108](https://user-images.githubusercontent.com/30411837/177044596-48343d77-8714-4943-ba10-6eddbd908d58.jpg)
![IMG_0109](https://user-images.githubusercontent.com/30411837/177044597-f6ba9411-55e7-4ef8-9104-803bd6b7bfa8.jpg)
![IMG_0110](https://user-images.githubusercontent.com/30411837/177044598-6f9a0326-5d4c-4dfb-8f40-e50bc69d52fd.jpg)
![IMG_0111](https://user-images.githubusercontent.com/30411837/177044584-47757ea8-683f-41c7-9393-09981a7aaa6d.jpg)

