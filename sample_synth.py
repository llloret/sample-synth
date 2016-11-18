import sys
import os
from multiprocessing import Process, Pipe
import pyaudio
import wave
import mido
import time


class MIDIOut:
    def __init__(self):
        mido.set_backend('mido.backends.rtmidi')
        outputs = mido.get_output_names()
        self.outport = mido.open_output(outputs[0])

    def send_note_on(self, note, velocity=127):
        msg = mido.Message('note_on', note=note, velocity=velocity)
        self.outport.send(msg)

    def send_note_off(self, note, velocity=0):
        msg = mido.Message('note_off', note=note, velocity=velocity)
        self.outport.send(msg)


# We assume stereo at 44kHz for now
class Recorder:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.channels = 2
        self.rate = 44100
        self.format = pyaudio.paInt24
        self.CHUNK = 1024

    # time is in seconds
    def record_and_save(self, seconds, filename):
        stream = self.p.open(input_device_index=5, format=self.format, channels=self.channels, rate=self.rate, input=True,
                             frames_per_buffer=self.CHUNK)

        print("* recording")
        frames = []
        for i in range(0, int(self.rate / self.CHUNK * seconds)):
            data = stream.read(self.CHUNK)
            frames.append(data)

        stream.stop_stream()
        stream.close()

        # Save file
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.p.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(frames))
        wf.close()

        print("* done recording")


def record_process(pipe_conn):
    recorder = Recorder()
    while True:
        msg = pipe_conn.recv()
        print("RECORD: received {0}".format(msg))
        if msg[0] == "exit":
            break

        print("RECORD: going to save 15s of audio in {0}".format(msg[1]))
        recorder.record_and_save(8, msg[1])
        print("RECORD: sending done")
        pipe_conn.send('done')


if __name__ == '__main__':
    NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    instrument_name = sys.argv[1]
    start_note = int(sys.argv[2])
    end_note = int(sys.argv[3])

    dirname = 'd:/tmp/' + instrument_name
    if not os.path.exists(dirname):
        os.mkdir(dirname)

    midiout = MIDIOut()
    parent_conn, child_conn = Pipe()
    p = Process(target=record_process, args=(child_conn,))
    p.start()

    for midinote in range(start_note, end_note + 1):
        print("MAIN: sending start")
        octave = str((midinote // 12) - 2)
        note = NOTES[midinote % 12]
        fullnote = note + octave
        parent_conn.send(['start', '{0}/{1}-{2}-{3}.wav'.format(dirname, instrument_name, fullnote, fullnote)])
        time.sleep(0.5)
        print("MAIN: sending note on")
        midiout.send_note_on(midinote, 127)
        time.sleep(5)
        print("MAIN: sending note off")
        midiout.send_note_off(midinote)
        print("MAIN: waiting for record to finish")
        msgrecv = parent_conn.recv()
        print("MAIN: received {0}".format(msgrecv))

    parent_conn.send(['exit'])
    p.join()
