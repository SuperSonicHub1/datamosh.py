#! /usr/bin/env python3

"""
A much cleaner version of https://github.com/happyhorseskull/you-can-datamosh-on-linux
that assumes you know how computers work. 
"""

from argparse import ArgumentParser, FileType, Namespace
import json
import subprocess
from sys import stdin, stdout, stderr, exit
# import os

# Byte constants

# signals the end of a frame
end_of_frame = bytes.fromhex('30306463')
# signals the beginning of an i-frame
i_frame = bytes.fromhex('0001B0')

def get_fps(input: str):
	process = subprocess.run(
		[
			"ffprobe",
			"-print_format", "json",
			"-show_streams",
			input,
		],
		capture_output=True,
	)

	check_process(process)

	info = json.loads(process.stdout)
	video_stream = [stream for stream in info["streams"] if stream["codec_type"] == "video"][0]
	return int(eval(video_stream["r_frame_rate"]))

def check_process(process: subprocess.CompletedProcess):
	try:
		process.check_returncode()
	except subprocess.CalledProcessError as e:
		raise Exception(process.stderr.decode()) from e

def datamosh(args: Namespace):
	input, output = args.input, args.output
	fps = args.fps if args.fps else get_fps(input)

	end_effect_sec = vars(args)["end-effect-sec"]
	start_effect_sec = vars(args)["start-effect-sec"]

	end_effect_hold = end_effect_sec - start_effect_sec
	start_effect_sec = start_effect_sec - args.start_sec
	end_effect_sec = start_effect_sec + end_effect_hold

	if start_effect_sec > end_effect_sec:
		print("No moshing will occur because --start_effect_sec begins after --end_effect_sec", file=stderr)
		exit(1)

	arguments = [
		"ffmpeg",
		"-loglevel", "error",
		"-xerror",
		"-y",
		"-i", input,
		"-crf", "0",
		"-pix_fmt", "yuv420p",
		"-r", str(fps),
		"-ss", str(args.start_sec),
	]

	if args.end_sec:
		arguments += ["-to", str(args.end_sec)]

	arguments += ["-f", "avi", "-"]

	avi_convert = subprocess.run(
		arguments,
		capture_output=True,
	)

	check_process(avi_convert)

	avi_bytes = avi_convert.stdout
	datamosh_bytes = bytes()

	frames = avi_bytes.split(end_of_frame)

	i_frame_yet = False

	for index, frame in enumerate(frames):
		if i_frame_yet == False or index < int(start_effect_sec * fps) or index > int(end_effect_sec * fps):
			# the split above removed the end of frame signal so we put it back in
			datamosh_bytes += frame + end_of_frame

			# found an i-frame, let the glitching begin
			if frame[5:8] == i_frame:
				i_frame_yet = True
		else:
			# while we're moshing we're repeating p-frames and multiplying i-frames
			if frame[5:8] != i_frame:
				# this repeats the p-frame x times
				for i in range(args.repeat_p_frames):
					datamosh_bytes += frame + end_of_frame

	mp4_convert = subprocess.run(
		[
			"ffmpeg",
			"-loglevel", "error",
			"-xerror",
			"-y",
			"-f", "avi",
			"-i", "-",
			# "-crf", "18",
			# "-pix_fmt", "yuv420p",
			# "-vcodec", "libx264",
			# "-acodec", "aac",
			"-r", str(fps),
			# "-vf", f'"scale={args.output_width}:-2:flags=lanczos"',
			# "-f", "mp4",
			output,
		],
		input=datamosh_bytes,
		capture_output=True,
		# shell=True,
	)

	check_process(mp4_convert)

if __name__ == "__main__":
	parser = ArgumentParser()

	parser.add_argument('start-effect-sec', type=float, help="Time the effect starts on the trimmed footage's timeline. The output video can be much longer.")
	parser.add_argument('end-effect-sec', type=float, help="Time the effect ends on the trimmed footage's timeline.")

	parser.add_argument('input', type=str)
	parser.add_argument('output', type=str)
	
	parser.add_argument('--start-sec', default=0.0, type=float, help="Time the video starts on the original footage's timeline. Trims preceding footage.")
	parser.add_argument('--repeat-p-frames', default=15, type=int, help="If this is set to 0 the result will only contain i-frames. Possibly only a single i-frame.")
	# Default is existing width of video.
	parser.add_argument('--output-width', default=0, type=int, help="Width of output video in pixels. 480 is Twitter-friendly. Default is the input width.")
	

	# Default is end of video
	parser.add_argument('--end-sec', default=None, help="Time on the original footage's time when it is trimmed. Default is end of video.")
	# Default is framerate of video
	parser.add_argument('--fps', default=None, help="The number of frames per second the initial video is converted to before moshing. Default is existing framerate of video.")

	args = parser.parse_args()
	datamosh(args)
