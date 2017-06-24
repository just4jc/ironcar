#!/usr/bin/env python

"""

drive.py receives control commands (from keyboard, gamepad or autopilot,
handled by remote_controller) and gives input to the car.

Launched on the Raspberry Pi

"""

import sys
import rospy
from std_msgs.msg import String, Float32, Bool
import Adafruit_PCA9685
import time
import picamera
import datetime
import os
from Adafruit_BNO055 import BNO055
from utils import ArgumentError, initialize_imu

# PWM setup
pwm = Adafruit_PCA9685.PCA9685()
pwm.set_pwm_freq(60)

def pic_cb(data):

    global n_img, curr_gas, curr_dir, drive, bno, save_folder

    x, y, z = bno.read_linear_acceleration()
    image_name = os.path.join(save_folder, 'frame_'+ str(n_img) + '_gas_' +
                                str(curr_gas) + '_dir_' + str(curr_dir) +
                                "_xacc_" + str(x) + "_yacc_" + str(y) +
                                "_zacc_" + str(z) +'_' + '.jpg')
    cam.capture(image_name, quality=10, resize=(250,150))
    n_img += 1

def dir_cb(data):

    global curr_dir, commands

    curr_dir = data.data

    if curr_dir == 0:
        pwm.set_pwm(commands['direction'], 0 , commands['straight'])
    else:
        pwm.set_pwm(commands['direction'], 0 , int(curr_dir * (commands['right'] - commands['left'])/2. + commands['straight']))


def gas_cb(data):
    global curr_gas, commands, reverse

    print('reverse : ', reverse)
    print('reverse_drive_max : ', commands['rev_drive_max'])
    curr_gas = data.data

    if reverse:
        if curr_gas < 0:
            print('0')
            print(commands['rev_neutral'])
            pwm.set_pwm(commands['gas'], 0 , commands['rev_neutral'])
        elif curr_gas == 0:
            print('1')
            print(commands['rev_neutral'])
            pwm.set_pwm(commands['gas'], 0 , commands['rev_neutral'])
        else:
            print('2')
            print(curr_gas)
            print(commands['rev_drive_max'])
            print(commands['rev_drive'])
            print(int(curr_gas * (commands['rev_drive_max']-commands['rev_drive']) + commands['rev_drive']))
            pwm.set_pwm(commands['gas'], 0 , int(curr_gas * (commands['rev_drive_max']-commands['rev_drive']) + commands['rev_drive']))
    else:
        if curr_gas < 0:
            pwm.set_pwm(commands['gas'], 0 , commands['stop'])
        elif curr_gas == 0:
            pwm.set_pwm(commands['gas'], 0 , commands['neutral'])
        else:
            pwm.set_pwm(commands['gas'], 0 , int(curr_gas * (commands['drive_max']-commands['drive']) + commands['drive']))


def change_dir_cb(data):
    global commands, reverse

    change_direction = data.data
    if change_direction:
        reverse = not reverse
        if reverse:
            pwm.set_pwm(commands['gas'], 0, 350)
            time.sleep(1)
            pwm.set_pwm(commands['gas'], 0, commands['rev_neutral'])
        else:
            pwm.set_pwm(commands['gas'], 0, 390)
            time.sleep(1)
            pwm.set_pwm(commands['gas'], 0, commands['neutral'])


def callback(data):
    global curr_gas, curr_dir, commands
    print('&'*25)
    print('curr_gas : ', curr_gas, 'curr_dir : ', curr_dir)
    received_command = data.data
    rospy.loginfo("just received: %s", received_command)
    print('commands : ', commands)
    if received_command == "left":
        pwm.set_pwm(commands['direction'], 0 , commands['left'])
        curr_dir = -1
    elif received_command == "right":
        pwm.set_pwm(commands['direction'], 0 , commands['right'])
        curr_dir = 1
    elif received_command in ["rightreleased", "leftreleased"]:
        pwm.set_pwm(commands['direction'], 0 , commands['straight'])
        curr_dir = 0
    elif received_command == "up":
        pwm.set_pwm(commands['gas'], 0 , commands['drive'])
        curr_gas = 0.5
    elif received_command == "down":
        pwm.set_pwm(commands['gas'], 0 , commands['stop'])
        curr_gas = 0
    elif received_command in ["upreleased", "downreleased"]:
        pwm.set_pwm(commands['gas'], 0 , commands['neutral'])
        curr_gas = 0


def initialize_motor(xacc_threshold):
    global step, commands, bno

    x = 0
    for k in range(0, 50, step):
        print(x)
        pwm.set_pwm(2, 0 , 360 + k)
        # TODO: what if there is not imu ?
        x, y, z = bno.read_linear_acceleration()
        time.sleep(0.3)
        if x > xacc_threshold:
            print("detected movement, setting straight to ", 360+k)
            pwm.set_pwm(2, 0 , commands['neutral'])
            time.sleep(2)
            drive = 360 + k + init_gas
            commands['drive'] = drive
            break

def main():

    global controls

    rospy.loginfo("Launching listeners")

    if controls == 'keyboard':
        print('Using keyboard')
        rospy.init_node('drive', anonymous=True)
        rospy.Subscriber("dir_gas", String, callback)
        rospy.Subscriber("pic", String, pic_cb)
        print("Ready, entering loop")
        rospy.spin()
    elif controls == 'gamepad':
        print('Using gamepad')
        rospy.init_node('drive', anonymous=True)
        rospy.Subscriber("dir", Float32, dir_cb)
        rospy.Subscriber("gas", Float32, gas_cb)
        rospy.Subscriber("pic", String, pic_cb)
        rospy.Subscriber("rev", Bool, change_dir_cb)
        print("Ready, entering loop")
        rospy.spin()
    elif controls == 'autopilot':
    	print('Running in autopilot !')
        rospy.loginfo("Launching listener")
        rospy.init_node('drive', anonymous=True)
        rospy.Subscriber("dir_gas", String, callback)
        print("Ready, entering loop")
        rospy.spin()

    else:
        print('No controller has been set: \n'
              'Current controller is {}'.format(controls))


if __name__ == '__main__':

    possible_arguments = ['-k', '--keyboard', '-a', '--autopilot', '-g',
                          '--gamepad', '-i', '--init-motor', '-s',
                          '--save-folder', '--no-imu']
    arguments = sys.argv[1:]

    controls = 'keyboard'
    init_motor = False
    init_imu = True

    # TODO
    commands = {'direction': 1, 'left': 310, 'right': 490, 'straight': 400,
                'gas': 2, 'drive': 400, 'stop': 210, 'neutral': 385,
                'drive_max': 420, 'rev_neutral': 370,
                'rev_drive': 360, 'rev_drive_max': 350, 'rev_stop': 400,
                'go_t': 0.25, 'stop_t': -0.25, 'left_t': 0.5, 'right_t': -0.5}

    ct = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    save_folder = os.path.join('videos/', str(ct))

    n_img = 0

    # cam setup
    print('Setting up the pi camera')
    cam = picamera.PiCamera()
    print('Pi camera set up')

    # PWM setup
    pwm = Adafruit_PCA9685.PCA9685()
    pwm.set_pwm_freq(60)

    # init_motor
    step = 2
    init_gas = 10

    curr_dir = 0
    curr_gas = 0
    reverse = False

    #IMU params
    xacc_threshold = 0.2
    bno = None

    i = 0
    while i < len(arguments):
        arg = arguments[i]
        if arg not in possible_arguments:
            raise ArgumentError
        elif arg in ['--no-imu']:
            init_imu = False
        elif arg in ['-k', '--keyboard']:
            controls = 'keyboard'
        elif arg in ['-g', '--gamepad']:
            controls = 'gamepad'
        elif arg in ['-a', '--autopilot']:
            controls = 'autopilot'
        elif arg in ['-i', '--init-motor']:
            init_motor = True
        elif arg in ['-s', '--save-file']:
            if i+1 >= len(arguments):
                print('No save file has been given.')
                print('Using the default one : ', save_folder)
            else:
                save_folder = arguments[i+1]
            if not os.path.exists(save_folder):
                os.makedirs(save_folder)
            i += 1
        i += 1

    if init_imu:
        bno = initialize_imu(5)

    if init_motor:
        initialize_motor(xacc_threshold)

    main()
