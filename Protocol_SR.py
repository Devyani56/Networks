# SimPy models for rdt_Sender and rdt_Receiver
# implementing the Go-Back-N Protocol

# Author: Devyani Remulkar, IIT Goa


import simpy
import random
import sys
from Packet import Packet  # Assuming Packet class is defined elsewhere

class rdt_Sender(object):
    
    def __init__(self, env):
        # Initialize variables and parameters
        self.env = env 
        self.channel = None
        
        # Some default parameter values
        self.data_packet_length = 10  # bits
        self.timeout_value = 10  # Default timeout value for the sender
        self.N =16 # Sender's Window size
        self.K = 16  # Packet Sequence numbers can range from 0 to K-1

        # State variables and parameters for the Selective Repeat Protocol
        self.base = 1  # Base of the current window 
        self.nextseqnum = 1  # Next sequence number
        self.sndpkt = {}  # A buffer for storing the packets to be sent
        self.acknowledged = {}  # Buffer to store acknowledgment status of packets

        # Other variables to maintain sender-side statistics
        self.total_packets_sent = 0
        self.num_retransmissions = 0

        # Timer-related variables
        self.timers = {}  # Store timers for each packet
        self.timer_is_running = False
    
    def rdt_send(self, msg):
        # This function is called by the sending application.
        
        # Check if the nextseqnum lies within the range of sequence numbers in the current window.
        # If it does, make a packet and send it, else, refuse this data.
        if(self.nextseqnum in [(self.base + i) % self.K for i in range(0, self.N)]):
            print("TIME:", self.env.now, "RDT_SENDER: rdt_send() called for nextseqnum=", self.nextseqnum, " within current window. Sending new packet.")
            # Create a new packet and store a copy of it in the buffer
            self.sndpkt[self.nextseqnum] = Packet(seq_num=self.nextseqnum, payload=msg, packet_length=self.data_packet_length)
            # Send the packet
            self.channel.udt_send(self.sndpkt[self.nextseqnum])
            self.total_packets_sent += 1
            # Start the timer for the packet
            self.start_timer(self.nextseqnum)
            # Update the nextseqnum
            self.nextseqnum = (self.nextseqnum + 1) % self.K
            return True
        else:
            print("TIME:", self.env.now, "RDT_SENDER: rdt_send() called for nextseqnum=", self.nextseqnum, " outside the current window. Refusing data.")
            return False
        
    def rdt_rcv(self, packt):
        # This function is called by the lower-layer when an ACK packet arrives
        
        if not packt.corrupted:
            # Check if we got an ACK for a packet within the current window.
            if packt.seq_num in self.sndpkt.keys():
                self.acknowledged[packt.seq_num] = True
                print("TIME:", self.env.now, "RDT_SENDER: Got an ACK", packt.seq_num, ".")
                self.stop_timer(packt.seq_num)
                # Move the window and reset acknowledgment status
                while self.base in self.acknowledged and self.acknowledged[self.base]:
                    del self.acknowledged[self.base]
                    self.base = (self.base + 1) % self.K
            else:
                print("TIME:", self.env.now, "RDT_SENDER: Got an ACK", packt.seq_num, " for a packet in the old window. Ignoring it.")
        else:
            # Got a corrupted packet
            print("TIME:", self.env.now, "RDT_SENDER: Got a corrupted ACK packet", packt.seq_num)
           
    
    def timer_behavior(self, seq_num):
        try:
            # Wait for timeout 
            self.timer_is_running = True
            yield self.env.timeout(self.timeout_value)
            self.timer_is_running = False
            # Take some actions 
            self.timeout_action(seq_num)
        except simpy.Interrupt:
            # Stop the timer
            self.timer_is_running = False
    
    def start_timer(self, seq_num):
        # Start the timer for the given sequence number
        if seq_num not in self.timers:
            self.timers[seq_num] = self.env.process(self.timer_behavior(seq_num))
            print("TIME:", self.env.now, "TIMER STARTED for packet", seq_num, "with a timeout of", self.timeout_value)
        else:
            print("TIME:", self.env.now, "TIMER ALREADY RUNNING for packet", seq_num)
	
	
    def stop_timer(self, seq_num):
        # Stop the timer for the given sequence number
        if seq_num in self.timers:
            if not self.timers[seq_num].triggered:
                self.timers[seq_num].interrupt()
                print("TIME:", self.env.now, "TIMER STOPPED for packet", seq_num)
                del self.timers[seq_num]
            else:
                print("TIME:", self.env.now, "TIMER ALREADY TRIGGERED for packet", seq_num)
        else:
            print("TIME:", self.env.now, "TIMER NOT FOUND for packet", seq_num)
			
    
    def timeout_action(self, seq_num):
        # Re-send the packet on timeout
        if seq_num in self.sndpkt:
            print("TIME:", self.env.now, "RDT_SENDER: TIMEOUT OCCURRED for packet", seq_num, ". Re-transmitting.")
            self.channel.udt_send(self.sndpkt[seq_num])
            self.num_retransmissions += 1
            self.total_packets_sent += 1
            del self.timers[seq_num]
            self.start_timer(seq_num)
    
    def print_status(self):
        print("TIME:", self.env.now, "Current window:", [(self.base + i) % self.K for i in range(0, self.N)],
              "base =", self.base, "nextseqnum =", self.nextseqnum)
        print("---------------------")

class rdt_Receiver(object):
    
    def __init__(self, env):
        
        # Initialize variables
        self.env = env 
        self.receiving_app = None
        self.channel = None

        # Some default parameter values
        self.ack_packet_length = 10  # bits
        self.K = 16  # Range of sequence numbers expected

        # Initialize state variables
        self.expectedseqnum = 1
        self.receiving_window = 16  # Receiver's Window size
        self.base = 1  # Base of the receiving window
        self.sndpkt = Packet(seq_num=0, payload="ACK", packet_length=self.ack_packet_length)
        self.total_packets_sent = 0
        self.num_retransmissions = 0
        self.received_packets = {}  # Buffer to store received packets within the window

    def rdt_rcv(self, packt):
        # This function is called by the lower-layer when a packet arrives at the receiver

        if not packt.corrupted:
            print("TIME:", self.env.now, "RDT_RECEIVER: got expected packet", packt.seq_num, ". Sent ACK", packt.seq_num)
            # Send acknowledgment for the received packet
            self.sndpkt = Packet(seq_num=packt.seq_num, payload="ACK", packet_length=self.ack_packet_length)
            self.channel.udt_send(self.sndpkt)
            self.total_packets_sent += 1

            if packt.seq_num in [(self.base + i) % self.K for i in range(0, self.receiving_window)]:
                # Extract and deliver data
                
                # Store the received packet in the buffer
                self.received_packets[packt.seq_num] = packt
                # Move the window ahead if the first packet in the window is received
                while self.base in self.received_packets:
                    self.receiving_app.deliver_data(self.received_packets[self.base].payload)
                    del self.received_packets[self.base]
                    self.base = (self.base + 1) % self.K
            else:
                # Packet received is not the expected one
                print("TIME:", self.env.now, "RDT_RECEIVER: got unexpected packet with sequence number", packt.seq_num, ". Sent ACK", packt.seq_num)
                self.num_retransmissions += 1
        else:
            # Got a corrupted packet
            print("TIME:", self.env.now, "RDT_RECEIVER: got corrupted packet", packt.seq_num)



           




