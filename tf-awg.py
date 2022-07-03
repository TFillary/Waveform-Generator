# Arbitrary waveform generator for Rasberry Pi Pico
# Requires 8-bit R2R DAC on pins 0-7. Works for R=2k2Ohm
# Achieves 125Msps when running 125MHz clock
# Based on AWG by Rolf Oldeman, 7/2/2021. CC BY-NC-SA 4.0 licence
# Modified for simpler awg, using rotary encoder switches and a small OLED display for control
# T.D.Fillary 20-03-22
from machine import Pin, mem32, Timer, I2C, freq
from rp2 import PIO, StateMachine, asm_pio
from array import array
from utime import sleep
from math import sin, pi
import time

timer = Timer()
from rotary_irq_rp2 import RotaryIRQ
from ssd1306 import SSD1306_I2C

DMA_BASE=0x50000000
CH0_READ_ADDR  =DMA_BASE+0x000
CH0_WRITE_ADDR =DMA_BASE+0x004
CH0_TRANS_COUNT=DMA_BASE+0x008
CH0_CTRL_TRIG  =DMA_BASE+0x00c
CH0_AL1_CTRL   =DMA_BASE+0x010
CH1_READ_ADDR  =DMA_BASE+0x040
CH1_WRITE_ADDR =DMA_BASE+0x044
CH1_TRANS_COUNT=DMA_BASE+0x048
CH1_CTRL_TRIG  =DMA_BASE+0x04c

PIO0_BASE     =0x50200000
PIO0_BASE_TXF0=PIO0_BASE+0x10
PIO0_SM0_CLKDIV=PIO0_BASE+0xc8

fclock = freq() #clock frequency of the pico
freq_set = 20000 #Default starting frequency
old_freq = freq_set 
cycle_bytes = 100  # 100 bytes per waveform cycle

def set_clock_div():
    div=fclock/(freq_set*cycle_bytes)
    clkdiv=int(div)
    clkdiv_frac=0 #fractional clock division results in jitter
    mem32[PIO0_SM0_CLKDIV]=(clkdiv<<16)|(clkdiv_frac<<8)

#state machine that just pushes bytes to the pins
@asm_pio(out_init=(PIO.OUT_HIGH,PIO.OUT_HIGH,PIO.OUT_HIGH,PIO.OUT_HIGH,PIO.OUT_HIGH,PIO.OUT_HIGH,PIO.OUT_HIGH,PIO.OUT_HIGH),
         out_shiftdir=PIO.SHIFT_RIGHT, autopull=True, pull_thresh=32)
def stream():
    out(pins,8)

# Start state machine before DMA set up - State machine set to pico default freq of 125Mhz, clock div controls the actual execution speed
sm = StateMachine(0, stream, freq=fclock, out_base=Pin(0))
sm.active(1)

set_clock_div() # set up state clock divisor for the streaming frequency required

#2-channel chained DMA. channel 0 does the transfer, channel 1 reconfigures
p_ar=array('I',[0]) #global 1-element array 
@micropython.viper
def startDMA(ar,nword):
    p=ptr32(ar)
    mem32[CH0_READ_ADDR]=p
    mem32[CH0_WRITE_ADDR]=PIO0_BASE_TXF0
    mem32[CH0_TRANS_COUNT]=nword
    IRQ_QUIET=0x1 #do not generate an interrupt
    TREQ_SEL=0x00 #wait for PIO0_TX0
    CHAIN_TO=1    #start channel 1 when done
    RING_SEL=0
    RING_SIZE=0   #no wrapping
    INCR_WRITE=0  #for write to array
    INCR_READ=1   #for read from array
    DATA_SIZE=2   #32-bit word transfer
    HIGH_PRIORITY=1
    EN=1
    CTRL0=(IRQ_QUIET<<21)|(TREQ_SEL<<15)|(CHAIN_TO<<11)|(RING_SEL<<10)|(RING_SIZE<<9)|(INCR_WRITE<<5)|(INCR_READ<<4)|(DATA_SIZE<<2)|(HIGH_PRIORITY<<1)|(EN<<0)
    mem32[CH0_AL1_CTRL]=CTRL0
    
    p_ar[0]=p
    mem32[CH1_READ_ADDR]=ptr(p_ar)
    mem32[CH1_WRITE_ADDR]=CH0_READ_ADDR
    mem32[CH1_TRANS_COUNT]=1
    IRQ_QUIET=0x1 #do not generate an interrupt
    TREQ_SEL=0x3f #no pacing
    CHAIN_TO=0    #start channel 0 when done
    RING_SEL=0
    RING_SIZE=0   #no wrapping
    INCR_WRITE=0  #single write
    INCR_READ=0   #single read
    DATA_SIZE=2   #32-bit word transfer
    HIGH_PRIORITY=1
    EN=1
    CTRL1=(IRQ_QUIET<<21)|(TREQ_SEL<<15)|(CHAIN_TO<<11)|(RING_SEL<<10)|(RING_SIZE<<9)|(INCR_WRITE<<5)|(INCR_READ<<4)|(DATA_SIZE<<2)|(HIGH_PRIORITY<<1)|(EN<<0)
    mem32[CH1_CTRL_TRIG]=CTRL1


#setup waveform arrays. frequency is 125MHz/nsamp
nsamp=100 #must be a multiple of 4
wave=array("I",[0]*nsamp) # Main output wave
sinewave=array("I",[0]*nsamp)
sawtoothwave=array("I",[0]*nsamp)
trianglewave=array("I",[0]*nsamp)
stairwave=array("I",[0]*nsamp)

#calculate values for each sample for each waveform to make it quicker to change waveforms
for isamp in range(nsamp):
    sineval=128+127*sin((isamp+0.5)*2*pi/nsamp)     #sine wave
    sawtoothval=isamp*255/nsamp                     #sawtooth
    triangleval=abs(255-isamp*510/nsamp)            #triangle
    stairval=int(isamp/20)*20*255/nsamp             #stairs

    sinewave[int(isamp/4)]+=(int(sineval)<<((isamp%4)*8))
    sawtoothwave[int(isamp/4)]+=(int(sawtoothval)<<((isamp%4)*8))
    trianglewave[int(isamp/4)]+=(int(triangleval)<<((isamp%4)*8))
    stairwave[int(isamp/4)]+=(int(stairval)<<((isamp%4)*8))

# Returns a squarewave array for the specified duty cycle
def setupsquare(duty):
    # Initialise the array to zero
    squarewave=array("I",[0]*nsamp)

    for isamp in range(nsamp): # sets up level 'high' first
        if isamp < duty:
            squareval = 0xff
        else:
            squareval = 0

        squarewave[int(isamp/4)]+=(int(squareval)<<((isamp%4)*8))
    return squarewave

# Copies the specified waveform to the main 'wave' output array being DMA'd
def selectwave(waveform):
    global wave
#    time.sleep(4)
    sm.active(0)
    for i in range(nsamp):
        wave[i] = waveform[i]
    
    sm.active(1) 

# Setup all of the duty cycle waveforms - one for every 10% duty cycle to simplify selection menu
squarewave10 = setupsquare(10)
squarewave20 = setupsquare(20)
squarewave30 = setupsquare(30)
squarewave40 = setupsquare(40)
squarewave50 = setupsquare(50)
squarewave60 = setupsquare(60)
squarewave70 = setupsquare(70)
squarewave80 = setupsquare(80)
squarewave90 = setupsquare(90)

# Default to sinewave to start with
selectwave(sinewave)

#start
startDMA(wave,int(nsamp/4))

#processor free to do anything else

# Init I2C using pins GP8 & GP9 (default I2C0 pins)
i2c = I2C(0, scl=Pin(17), sda=Pin(16), freq=200000)

# Display device address
#print("I2C Address      : "+hex(i2c.scan()[0]).upper())
#print("I2C Configuration: "+str(i2c))                   # Display I2C config

oled = SSD1306_I2C(128, 64, i2c)                  # Init oled display

# Setup selection waveform arrays
waveforms = ["sine", "triangle", "sawtooth", "step", "square-10/90", "square-20/80", 
             "square-30/70", "square-40/60", "square-50/50", "square-60/40", "square-70/30", 
             "square-80/20", "square-90/10"]

waveforms_arr = [sinewave, trianglewave, sawtoothwave, stairwave, squarewave10, squarewave20, 
                 squarewave30, squarewave40, squarewave50, squarewave60, squarewave70, squarewave80, squarewave90]

selected_waveform = 0 #defaults to sine

freq_mult = ["x1", "x10", "x100", "x1K", "x10K", "x100K", "x1M"]
freq_mult_val = [1, 10, 100, 1000, 10000, 100000, 1000000]
selected_freq_mult = 4 # Default to x10K

CHANGE_FREQ = True
CHANGE_MULT = False
freq_mult_mode = CHANGE_FREQ

def update_display():
    # Clear the oled display in case it has junk on it.
    oled.fill(0)

    oled.text("Frequency Gen", 10, 2)
    # Add some text
    if freq_mult_mode == CHANGE_FREQ:
        pad = ">"
    else:
        pad = " "
    freq_text = pad+"f = "+f"{freq_set:,}"+"hz"
    #oled.text(freq_text,1,8)
    oled.text(freq_text,1,20)
    if freq_mult_mode == CHANGE_MULT:
        pad = ">"
    else:
        pad = " "
    freq_mult_text = pad+"Mult = "+freq_mult[selected_freq_mult]
    #oled.text(freq_mult_text,1,18)
    oled.text(freq_mult_text,1,30)
    wave_text = "Wave = "+waveforms[selected_waveform]
    oled.text(wave_text,1,50)
    #oled.text(wave_text,1,40)
    

    # Finally update the oled display so the image & text is displayed
    oled.show()

update_display()

# Setup the rotary encoders + switches
sw1 = Pin(26, Pin.IN, Pin.PULL_UP)
sw2 = Pin(20, Pin.IN, Pin.PULL_UP)

# Apply all of the freq/waveform settings 
def pinhandler1(pin):
    set_clock_div() # Adjust frequency as needed
    selectwave(waveforms_arr[selected_waveform]) # Setup required waveform
    
    #print('pushed r1',selected_waveform)

def pinhandler2(pin):
    global freq_mult_mode
    freq_mult_mode = not freq_mult_mode
    update_display()
    #print('pushed r2')


def debounce1(pin):
    timer.init(mode=Timer.ONE_SHOT, period=200, callback=pinhandler1)

def debounce2(pin):
    timer.init(mode=Timer.ONE_SHOT, period=200, callback=pinhandler2)

sw1.irq(handler=debounce1, trigger=Pin.IRQ_FALLING)
sw2.irq(handler=debounce2, trigger=Pin.IRQ_FALLING)

# Note clk/dt pins equate to a & b on the switch
# r1 selects the waveform + actions all selections and r2 selects the frequency/multiplier
r1 = RotaryIRQ(pin_num_clk=28, 
              pin_num_dt=27, 
              min_val=0, 
              max_val=len(waveforms)-1, 
              reverse=False,
              pull_up=True,
              range_mode=RotaryIRQ.RANGE_WRAP)

r2 = RotaryIRQ(pin_num_clk=22, 
              pin_num_dt=21, 
              min_val=0, 
              max_val=10, 
              reverse=False,
              pull_up=True,
              range_mode=RotaryIRQ.RANGE_UNBOUNDED)

# Setup initial switch values
r1_old = r1.value()
r2_old = r1.value()

def new_freq_mult(dir):
    # Update either the frequency value or the frequency multiplier index
    global selected_freq_mult, freq_set
    if freq_mult_mode == CHANGE_FREQ:
        freq_set = freq_set + (freq_mult_val[selected_freq_mult] * dir)
        # Limit max/min frequency
        if freq_set > 1000000:
            freq_set = 1000000 # Limit to 1Mhz
        elif freq_set <= 0:
            freq_set = 20 # Minimum seems to be 20Hz

    else: # Change multiplication value
        selected_freq_mult += dir
        # Wrap index through max & min values
        if selected_freq_mult == len(freq_mult):
            selected_freq_mult = 0
        elif selected_freq_mult == -1:
            selected_freq_mult = len(freq_mult)-1

    update_display() # Update the display but don't set new waveform until frequency set too
    #print(freq_set, selected_freq_mult)
    #print('pushed r2')

while True:

    # Loop around checking the rotary stitches
    r1_new = r1.value()
    r2_new = r2.value()
    
    if r1_old != r1_new:
        selected_waveform = r1_new # switch automatically wraps
        r1_old = r1_new
        update_display() # Update the display but don't set new waveform until frequency set too
        #print('result r1 =', r1_new)

    if r2_old != r2_new:
        if r2_new > r2_old: # Increase
            dir = 1
        else:
            dir = -1

        r2_old = r2_new
        # Update either the frequency or mult factor depending on mode
        new_freq_mult(dir)


