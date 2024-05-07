# Required libraries
from time import sleep
import numpy as np
from scipy.interpolate import PchipInterpolator
import paho.mqtt.client as mqtt
import control as ct
import struct
from queue import Queue
import math
import json
from pathlib import Path
import csv
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("TkAgg", force=True)


# These are the parameters of communication

#BROKER = "broker.hivemq.com"
BROKER = "192.168.0.3"
#BROKER = "18.204.70.207" # amazon mosquitto broker
PORT = 1883
USER = "hpdesktop"
PASSWORD = "hpdesktop"




#topics for subscription

PLANT_NUMBER = "5678"
codes ={"SYS_USER_SIGNALS_CLOSED"  : "/motor/motor_" + PLANT_NUMBER + "/user/sig_closed",
        "SYS_USER_SIGNALS_OPEN"  : "/motor/motor_" + PLANT_NUMBER + "/user/sig_open",
        "USER_SYS_SET_REF"  : "/motor/user/motor_" + PLANT_NUMBER + "/set_ref",
        "USER_SYS_SET_PID"  : "/motor/user/motor_" + PLANT_NUMBER  + "/set_pid",
        "USER_SYS_STEP_CLOSED": "/motor/user/motor_" + PLANT_NUMBER +"/step_closed",
        "USER_SYS_STAIRS_CLOSED": "/motor/user/motor_" + PLANT_NUMBER + "/stairs_closed",
        "USER_SYS_PRBS_OPEN": "/motor/user/motor_" + PLANT_NUMBER + "/prbs_open",
        "USER_SYS_STEP_OPEN": "/motor/user/motor_" + PLANT_NUMBER + "/step_open",
        "USER_SYS_SET_GENCON": "/motor/user/motor_" + PLANT_NUMBER + "/set_gencon",
        "USER_SYS_PROFILE_CLOSED": "/motor/user/motor_" + PLANT_NUMBER + "/prof_closed",
        "MOTOR_SAMPLING_TIME" : 0.02,
        "BUFFER_SIZE" : 25,
        }



PATH = r"./experiment_files/"



""" This is the class defining the IoT motor system"""
class MotorSystemIoT:

    def __init__(self, broker_address = BROKER, port= PORT, client_id="", clean_session=True):
        self.client = mqtt.Client()
        self.broker_address = broker_address
        self.port = port
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        self.client.on_publish = self.on_publish
        self.codes = codes


    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected successfully to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print("Unexpected disconnection.")

    def on_message(self, client, userdata, message):
        print(f"Received  '{message.payload.decode()}'")

    def on_subscribe(self, client, userdata, mid, granted_qos):
        print("Subscribed: ", mid, " ", granted_qos)

    def on_publish(self, client, userdata, mid):
        print("Message Published: ", mid)

    def connect(self):
        self.client.username_pw_set(USER, PASSWORD)
        self.client.connect(self.broker_address, self.port)
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def subscribe(self, topic, qos=2):
        self.client.subscribe(topic, qos)

    def publish(self, topic, message, qos=1):
        self.client.publish(topic, message, qos)

    def transfer_function(self, output='position', min_order=True):
        if output == 'position':
            if min_order:
                num = [4369.0278678492]
                den = [1, 9.97077548888435, 0]
            else:
                num = [798289.164111307]
                den = [1, 187.699939287416, 1803.62183871806, 0]

        elif output == 'velocity':
            if min_order:
                num = [4369.0278678492]
                den = [1, 9.97077548888435]
            else:
                num = [798289.164111307]
                den = [1, 187.699939287416, 1803.62183871806]

        G = ct.tf(num, den)
        return G

    def speed_from_volts(self, volts = None):
        if volts == None:
            raise ValueError("voltage input is required")

        u, y = read_csv_file()
        interp = PchipInterpolator(u, y)
        return interp(volts)

    def volts_from_speed(self, speed = None):
        if speed == None:
            raise ValueError("speed input is required")

        u, y = read_csv_file()
        interp = PchipInterpolator(u, y)
        if speed == 0:
            uc = 0
        elif (speed >= y[0]) and (speed <= y[-1]):
            roots = interp.solve(speed, extrapolate=False)
            uc = np.mean(roots)
        else:
            raise ValueError(f"The speed input must be in the interval {y[0]} to {y[-1]}")
        return uc



def float2hex(value):
    val_binary = struct.pack('>f', value)
    return val_binary.hex()


def long2hex(value):
    val_binary = struct.pack('>L', value)
    return val_binary.hex()


def hex2float(str):
    value = struct.unpack('!f', bytes.fromhex(str))[0]
    return value


def hex2long(str):
    value = struct.unpack('!L', bytes.fromhex(str))[0]
    return value


def signal2hex(signal):
    hstring = ""
    for point in signal:
        hstring += float2hex(point)
    return hstring


def time2hex(time_points):
    hstring = ""
    for t in time_points:
        hstring += long2hex(t)
    return hstring


def matrix2hex(matrix):
    hstring = ""
    for row in matrix:
        for element in row:
            hstring += float2hex(element)
    return hstring

def hexframe_to_array(hexframe):
    hexlist = hexframe.split(",")
    array = [hex2float(p) for p in hexlist]
    return array


def read_csv_file(filepath=PATH + 'static_gain_response.csv'):
    with open(filepath , newline='') as file:
        reader = csv.reader(file)
        # Iterate over each row in the CSV file
        num_line = 0
        u = []
        y = []
        for row in reader:
            if num_line != 0:
               u.append(float(row[0]))
               y.append(float(row[1]))
            num_line += 1
        return u, y


def set_reference(system, ref_value=50):
    ref_hex = float2hex(ref_value)
    topic_pub = system.codes["USER_SYS_SET_REF"]
    message = json.dumps({"reference": ref_hex})
    system.connect()
    system.publish(topic_pub, message)
    system.disconnect()
    rcode = True
    return rcode


def set_pid(system, kp=1, ki=0.4, kd=0, N=5, beta=1, output = "angle", deadzone = 0.125):

    if output == "angle":
        type_control = 0
    elif output == "speed":
        type_control = 1
    else:
        raise ValueError("valid value for output is 'angle' or 'speed'")

    topic_pub = system.codes["USER_SYS_SET_PID"]
    kp_hex = float2hex(kp)
    ki_hex = float2hex(ki)
    kd_hex = float2hex(kd)
    N_hex = float2hex(N)
    beta_hex = float2hex(beta)
    type_control_hex = long2hex(type_control)
    deadzone_hex = float2hex(deadzone)

    message = json.dumps({"kp": kp_hex,
                          "ki": ki_hex,
                          "kd": kd_hex,
                          "N": N_hex,
                          "beta": beta_hex,
                          "typeControl": type_control_hex,
                          "deadzone": deadzone_hex})
    system.connect()
    system.publish(topic_pub, message)
    system.disconnect()
    rcode = True
    print("succesfull change of PID parameters")
    return rcode


def step_closed(system, r0=0 , r1=100, t0=0 ,  t1=1, filepath = PATH + "DCmotor_step_closed_exp.csv"):

    def step_message(system, userdata, message):
        # This inner function is the callback of the received messages
        q.put(message)

    low_val = r0
    high_val = r1
    low_time = t0
    high_time = t1

    # reading the configuration parameters from the
    # dictionary of codes
    topic_pub = system.codes["USER_SYS_STEP_CLOSED"]
    topic_sub = system.codes["SYS_USER_SIGNALS_CLOSED"]
    sampling_time = system.codes["MOTOR_SAMPLING_TIME"]
    buffer = system.codes["BUFFER_SIZE"]

    # setting the parameters of the step response for sending to ESP32

    points_high = round(high_time / sampling_time)
    points_low = round(low_time / sampling_time)
    total_points = points_low + points_high
    frames = math.ceil(total_points/buffer)
    points_low_hex = long2hex(points_low)
    points_high_hex = long2hex(points_high)
    low_val_hex = float2hex(low_val)
    high_val_hex = float2hex(high_val)

    # command sent to ESP32 for obtaining the step response

    message = json.dumps({"low_val": low_val_hex,
                          "high_val": high_val_hex,
                          "points_low": points_low_hex,
                          "points_high": points_high_hex,
                          })

    # setting the callback for receiving messages
    system.client.on_message = step_message
    system.connect()
    system.subscribe(topic_sub)

    # sending the step_closed command through mqtt when config has been done
    system.publish(topic_pub, message)

    # vectors for storing the results and the experiment
    y = []
    r = []
    u = []
    t = []
    exp = []

    # Setting the graphics configuration for visualizing the experiment
    fig, (ay, au) = plt.subplots(nrows=2, ncols=1, width_ratios = [1], height_ratios= [4,1], figsize=(16, 9))
    fig.set_facecolor('#b7c4c8f0')

    # settings for the upper axes, depicting the model and speed data
    ay.set_title(f'Closed loop step response experiment with an initial value of  $r_0=${r0:0.2f} and a  final value of $r_0=${r1:0.2f}')
    ay.set_ylabel('Degrees/s (or Degrees)')
    ay.grid(True);
    ay.grid(color='#806600ff', linestyle='--', linewidth=0.25)
    ay.set_facecolor('#f4eed7ff')
    ay.set_xlim(0, t0 + t1  - sampling_time)

    #Setting the limits of figure
    py = 0.3
    delta_r = abs(r1 - r0)
    ylimits = [r0 , r1]
    ylimits = [np.min(ylimits), np.max(ylimits)]
    ay.set_ylim(ylimits[0] - py * delta_r, ylimits[1] + py * delta_r)

    au.set_facecolor('#d7f4e3ff')
    au.set_ylim(-5, 5)
    au.set_xlim(0, t0 + t1 - sampling_time )
    au.grid(color='#008066ff', linestyle='--', linewidth=0.25)


    line_r, = ay.plot(t, r, drawstyle='steps-post', color="#008066ff", linewidth=1.25) # drawstyle='steps'
    line_y, = ay.plot(t, y, color="#ff0066ff")
    line_u, = au.plot(t, u, color="#0066ffff")

    ay.legend([line_r, line_y], ['$r(t)$ (reference)', '$y(t)$ (output)'], fontsize=16, loc ="upper left")
    au.legend([line_u], ['$u(t)$ (control signal)'], fontsize=14)
    plt.draw()




    # this is the queue of messages filled by the step_message callback
    q = Queue()

    # at start we define a current frame of -1 indicating that no frame
    # has already been received
    curr_frame = -1
    while curr_frame < frames:
        try:
            message = q.get(True, 20* buffer * sampling_time)
        except:
            raise TimeoutError("The connection has been lost. Please try again")
        decoded_message = str(message.payload.decode("utf-8"))
        msg_dict = json.loads(decoded_message)
        frame_hex = str(msg_dict["frame"])
        curr_frame = hex2long(frame_hex)
        rframe_hex =  str(msg_dict["r"])
        uframe_hex = str(msg_dict["u"])
        yframe_hex = str(msg_dict["y"])
        rframe = hexframe_to_array(rframe_hex)
        uframe = hexframe_to_array(uframe_hex)
        yframe = hexframe_to_array(yframe_hex)
        tframe = sampling_time * (np.arange(len(rframe)) + (curr_frame - 1) * buffer)

        for ind in range(len(rframe)):
            r.append(rframe[ind])
            y.append(yframe[ind])
            u.append(uframe[ind])
            t.append(tframe[ind])
            exp.append([tframe[ind], rframe[ind], yframe[ind], uframe[ind]])
            line_r.set_data(t, r)
            line_y.set_data(t, y)
            line_u.set_data(t, u)
            plt.draw()
            plt.pause(sampling_time)


    np.savetxt(filepath, exp, delimiter=",",
                fmt="%0.8f", comments="", header='t,r,y,u')
    system.disconnect()
    plt.show()
    return t, y, r, u


def stairs_closed(system, stairs=[40, 50, 60], duration= 2, filepath = PATH + "DCmotor_stairs_closed_exp.csv"):
    def stairs_message(system, userdata, message):
        q.put(message)

    # reading the configuration parameters from the code's field in the plant

    topic_pub = system.codes["USER_SYS_STAIRS_CLOSED"]
    topic_sub = system.codes["SYS_USER_SIGNALS_CLOSED"]
    sampling_time = system.codes["MOTOR_SAMPLING_TIME"]
    buffer = system.codes["BUFFER_SIZE"]

    # setting the parameters of the step response for sending to ESP32

    points_stairs = len(stairs)
    points_stairs_hex = long2hex(points_stairs)
    signal_hex = signal2hex(stairs)
    duration = math.ceil(duration / sampling_time)
    duration_hex = long2hex(duration)

    min_val = npy.min(stairs)
    max_val = npy.max(stairs)
    min_val_hex = float2hex(min_val)
    max_val_hex = float2hex(max_val)

    # command sent to ESP32 for obtaining the step response
    message = json.dumps({"signal": signal_hex,
                          "duration": duration_hex,
                          "points_stairs": points_stairs_hex,
                          "min_val": min_val_hex,
                          "max_val": max_val_hex
                          })


    system.client.on_message = stairs_message

    # connecting system
    system.connect()

    # topic received from ESP32
    system.subscribe(topic_sub)

    # command sent to ESP32 for obtaining the stairs response
    system.publish(topic_pub, message)


    total_points = points_stairs * duration - 1
    frames = math.ceil(total_points / buffer)


    # vectors for storing the results of the experiment
    y = []
    r = []
    u = []
    t = []
    exp = []

    # Setting the graphics configuration for visualizing the experiment

    fig, ax = plt.subplots(nrows=2, ncols=1, width_ratios = [1], height_ratios= [4,1], figsize=(16, 9))
    ax.grid(True);
    ax.grid(color='gray', linestyle='--', linewidth=0.25)
    line_r, = ax.plot(t, r, drawstyle='steps-post', color="#338000")
    line_y, = ax.plot(t, y, drawstyle='steps-post', color="#d40055")
    ax.set_xlim(0, sampling_time * (total_points - 1))
    min_val = npy.min(stairs)
    max_val = npy.max(stairs)
    spany = max_val - min_val
    ax.set_ylim( min_val-0.1*abs(spany), max_val + 0.1* spany)
    line_r.set_data(t, r)
    line_y.set_data(t, y)
    plt.draw()

    # This is the queue of messages filled by the stair_message callback
    q = Queue()

    # At beginning we define a current frame of -1 indicating that no frame
    # has already been received
    curr_frame = -1

    # loop for receiving dataframes from the ESP32

    while curr_frame < frames:
        try:
            # we wait for 10 seconds for a new dataframe
            message = q.get(True, 20 * buffer * sampling_time)
        except:
            # else we raise a communication error
            raise TimeoutError("The connection has been lost. Please try again")

        # decoding the message
        decoded_message = str(message.payload.decode("utf-8"))
        msg_dict = json.loads(decoded_message)
        frame_hex = str(msg_dict["frame"])
        curr_frame = hex2long(frame_hex)
        rframe_hex = str(msg_dict["r"])
        uframe_hex = str(msg_dict["u"])
        yframe_hex = str(msg_dict["y"])
        rframe = hexframe_to_array(rframe_hex)
        uframe = hexframe_to_array(uframe_hex)
        yframe = hexframe_to_array(yframe_hex)
        tframe = sampling_time * (npy.arange(len(rframe)) + (curr_frame - 1) * buffer)

        # we plot every single point received in each dataframe
        # and save it in the matrix exp for storing in a csv file
        for ind in range(len(rframe)):
            #storing t, r, y, and u vectors
            r.append(rframe[ind])
            y.append(yframe[ind])
            u.append(uframe[ind])
            t.append(tframe[ind])

            # storing the experiment
            exp.append([tframe[ind], rframe[ind], yframe[ind], uframe[ind]])
            line_r.set_data(t, r)
            line_y.set_data(t, y)

            # drawing a new point from the current dataframe
            plt.draw()
            plt.pause(sampling_time)

    # Now, we save the results of the experiment in the provided filepath
    npy.savetxt(filepath, exp, delimiter=",",
                fmt="%0.8f", comments="", header='t,r,y,u')
    # Now all is done, close the connection and close the figure.
    system.disconnect()
    return t, y, r, u


def set_controller(system, controller, output='angle', struct=1):

    if (output == "angle") & (struct == 1):
        type_control = 2
    elif (output == "speed") & (struct == 1) :
        type_control = 3
    elif (output == "angle") & (struct == 2):
        type_control  = 4
    elif (output == "speed") & (struct == 2):
        type_control  = 5
    else:
        raise ValueError("valid value for output is 'angle' or 'speed'")


    topic_pub = system.codes["USER_SYS_SET_GENCON"]
    sampling_time = system.codes["MOTOR_SAMPLING_TIME"]
    Cvecont = ct.tf2ss(controller)
    order = len(Cvecont.A)
    Cve = ct.c2d(Cvecont, sampling_time, method='tustin')
    Ai, Bi, Ci, Di = Cve.A, Cve.B[:, 0], Cve.C,  Cve.D[0]
    int_system  = ct.ss(Ai, Bi, Ci, Di)
    int_system, T = ct.canonical_form(int_system)
    Cve = ct.similarity_transform(Cve,T)
    A = Cve.A
    B = Cve.B
    Cc = Cve.C
    Dc = Cve.D
    In = np.diag([100 for i in range(order)])
    L, S, E = ct.dlqr(np.transpose(A), np.transpose(Cc), In, 1)
    #P = [0.6 + 0.001*j for j in range(order)]
    #L = ct.place(np.transpose(A), np.transpose(Cc), P)
    L = np.transpose(L)
    Ac = A - L * Cc
    Bc = B - L * Dc
    if (np.size(Bc, axis=1)) == 1:
        B1 = []
        for row in Bc:
            for e in row:
                B1.append([e, -e])
        Bc = np.array(B1)
        Dc = np.array([[Dc[0][0], -Dc[0][0]]])
    A_hex = matrix2hex(Ac)
    B_hex = matrix2hex(Bc)
    C_hex = matrix2hex(Cc)
    D_hex = matrix2hex(Dc)
    L_hex = matrix2hex(L)
    order_hex = long2hex(order)
    type_control_hex = long2hex(type_control)
    message = json.dumps({"order": order_hex,
                          "A": A_hex,
                          "B": B_hex,
                          "C": C_hex,
                          "D": D_hex,
                          "L": L_hex,
                          "typeControl": type_control_hex})

    system.connect()
    system.publish(topic_pub, message)
    system.disconnect()
    rcode = True
    return rcode



def profile_closed(system, timevalues = [0, 1, 2 ,3], refvalues = [0, 720, 720, 0], filepath=PATH+"DCmotor_profile_closed_exp.csv"):
    def profile_message(system, userdata, message):
        # This is the callback for receiving messages from the plant
        q.put(message)

    # reading the configuration parameters from the code's field in the plant

    topic_pub = system.codes["USER_SYS_PROFILE_CLOSED"]
    topic_sub = system.codes["SYS_USER_SIGNALS_CLOSED"]
    sampling_time = system.codes["MOTOR_SAMPLING_TIME"]
    buffer = system.codes["BUFFER_SIZE"]

    # setting the parameters of the step response for sending to ESP32

    int_timevalues = [round(p/0.02) for p in timevalues]
    if int_timevalues[0] != 0:
        int_timevalues.insert(0, int_timevalues[0]-1)
        int_timevalues.insert(0,0)
        refvalues.insert(0,0)
        refvalues.insert(0,0)


    int_timevalues_hex = time2hex(int_timevalues)
    refvalues_hex = signal2hex(refvalues)
    points = len(int_timevalues)
    points_hex = long2hex(points)

    # user's command for obtaining the profile
    # al values are transmitted in hexadecimal
    min_val = np.min(refvalues)
    max_val = np.max(refvalues)
    min_val_hex = float2hex(min_val)
    max_val_hex = float2hex(max_val)

    message = json.dumps({"timevalues":  int_timevalues_hex,
                          "refvalues":   refvalues_hex,
                          "points":      points_hex,
                          "min_val":     min_val_hex,
                          "max_val":     max_val_hex,
                          })

    # setting the callback fro receiving data from the ESP32 for obtaining the profile response
    system.client.on_message = profile_message

    # connecting the system
    system.connect()

    # subscribing to topic published by ESP32
    system.subscribe(topic_sub)

    # command sent to ESP32 for obtaining the profile response
    system.publish(topic_pub, message)

    # setting the total of points and the total of frames
    total_points = int_timevalues[-1] + 1
    frames = math.ceil(total_points / buffer)

    # vectors for storing the results of the experiment
    y = []
    r = []
    u = []
    t = []
    exp = []

    # Setting the graphics configuration for visualizing the experiment

    fig, ax = plt.subplots(figsize=(16, 9))
    # settings for the upper axes, depicting the model and speed data
    ax.set_title(f'Profile experiment with {len(timevalues):d} points and a duration of {timevalues[-1]:0.2f} seconds' )
    ax.set_ylabel('Degrees/s (or Degrees)')
    ax.set_xlabel('Time (seconds)')
    ax.grid(color='#806600ff', linestyle='--', linewidth=0.25)
    ax.set_facecolor('#f4eed7ff')
    line_r, = ax.plot(t, r,  color="#005544ff", linewidth=1.25)
    line_y, = ax.plot(t, y,  color="#d45500ff", linewidth=1.25)
    ax.legend([line_r, line_y], ['$r(t)$ (reference)', '$y_R(t)$ (output)'], fontsize=16)
    ax.set_xlim(0, sampling_time * (total_points - 1))
    spany = max_val - min_val
    ax.set_ylim( min_val-0.1*abs(spany), max_val + 0.1* spany)
    line_r.set_data(t, r)
    line_y.set_data(t, y)
    plt.draw()

    # This is the queue of messages filled by the stair_message callback
    q = Queue()

    # At beginning we define a current frame of -1 indicating that no frame
    # has already been received
    curr_frame = -1

    # loop for receiving dataframes from the ESP32
    while curr_frame < frames:
        try:
            # we wait for 10 seconds for a new dataframe
            message = q.get(True, 20 * buffer * sampling_time)
        except:
            # else we raise a communication error
            raise TimeoutError("The connection has been lost. Please try again")

        # decoding the message
        decoded_message = str(message.payload.decode("utf-8"))
        msg_dict = json.loads(decoded_message)
        frame_hex = str(msg_dict["frame"])
        curr_frame = hex2long(frame_hex)
        rframe_hex = str(msg_dict["r"])
        uframe_hex = str(msg_dict["u"])
        yframe_hex = str(msg_dict["y"])
        rframe = hexframe_to_array(rframe_hex)
        uframe = hexframe_to_array(uframe_hex)
        yframe = hexframe_to_array(yframe_hex)
        tframe = sampling_time * (np.arange(len(rframe)) + (curr_frame - 1) * buffer)

        # we plot every single point received in each dataframe
        # and save it in the matrix exp, which allows to write a csv file
        for ind in range(len(rframe)):
            #storing t, r, y, and u vectors
            r.append(rframe[ind])
            y.append(yframe[ind])
            u.append(uframe[ind])
            t.append(tframe[ind])

            # storing the experiment
            exp.append([tframe[ind], rframe[ind], yframe[ind], uframe[ind]])
            line_y.set_data(t, y)
            line_r.set_data(t, r)


            # drawing a new point from the current dataframe
            plt.draw()
            plt.pause(sampling_time)
    PATH1 = r'/home/leonardo/sharefolder/ProyectoSabatico/Reporte/figures/'
    plt.savefig(PATH1 + "ProfileMotor.svg", format="svg", bbox_inches="tight")
    plt.show()
    Path(PATH).mkdir(exist_ok=True)
    # Now, we save the results of the experiment in the provided filepath
    np.savetxt(filepath , exp, delimiter=",",
                fmt="%0.8f", comments="", header='t,r,y,u')
    # Now all is done, close the connection and close the figure.
    system.disconnect()
    return t, y, r, u

def read_model_pbrs():
    with open(PATH + 'DCmotor_fo_model_pbrs.csv', newline='') as file:
        reader = csv.reader(file)
        # Iterate over each row in the CSV file
        num_line = 0
        for row in reader:
            if num_line != 0:
               alpha = float(row[0])
               tau = float(row[1])
            num_line += 1
        return alpha, tau

if __name__ == "__main__":
    motor1 = MotorSystemIoT()

    #set_pid(motor1, kp=0.042648109526048, ki=0, kd=0, N=11.9, beta=1, output = "angle")
    #step_closed(motor1, low_val=000, high_val=100, low_time=1.5, high_time=2)


    #resp_u = stepinfo(100 * Gur);
    #umax = resp_u.Peak

    #get_static_model(motor1, lowval=1.5)
    #val = motor1.volts_from_speed(200)
    #print(get_fomodel_step(motor1,-401))
    # print(motor1.volts_from_speed(1.15*400))
    # print(motor1.volts_from_speed(0.85*400))





    #u = 1
    #motor1.get_steady_state_curve(lowval=1.5)


    # t = [0, 1, 2, 3, 4 , 5, 6, 40]
    # y = [0, 1 , 1 , 2, 1, 1,0,1 ]
    # y = [yi *720 for yi in y]
    #
    #
    # profile_closed(motor1, t, y )

    #signal = [0, 45, 90, 135, 180, 135, 90, 45, 0]
    #stairs_closed(motor1 , signal, 2)
    # u = np.linspace(-5,5,100);
    # y=motor1.actuator_gain(u)
    # plt.plot(u,y)
    # plt.show()


    #stairs_closed(motor1, signal, 1.5)
    # #print(plant.transfer_function(output='velocity'))
    #set_pid(motor1, kp=0.026048, ki=0.028115, kd=0.00074865, N=11.9, beta=0.9)
    #sleep(1)

    #step_closed(motor1, low_val=0, high_val=90, low_time=1, high_time=2)

    #step_open(motor1, low_val= 0, high_val =5, low_time=1, high_time=1)

    #pbrs_open(motor1)
    #stairs_closed(motor1, signal, 4)

