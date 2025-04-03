import logging
import asyncio
import mini.mini_sdk as Mini
from mini.dns.dns_browser import WiFiDevice
from mini.apis.api_observe import ObserveInfraredDistance, ObserveSpeechRecognise
from mini.pb2.codemao_observeinfrareddistance_pb2 import ObserveInfraredDistanceResponse
from mini.pb2.codemao_speechrecognise_pb2 import SpeechRecogniseResponse
from mini.apis.api_sound import StartPlayTTS
from mini.apis.base_api import MiniApiResultType
from mini import MoveRobotDirection

# Logging information
Mini.set_log_level(logging.INFO)
Mini.set_log_level(logging.DEBUG)
Mini.set_robot_type(Mini.RobotType.EDU)

# Global flag to control movement interruption
STOP_MOVE_SEQUENCE = False

# Function for Text-to-Speech
async def play_tts(text: str):
    """Plays a text-to-speech message."""
    block: StartPlayTTS = StartPlayTTS(text=text)
    resultType, response = await block.execute()
    print(f'TTS Response: {resultType}, Message: {response}')

# Function to move the robot
async def move_robot(direction: MoveRobotDirection, step: int):
    """Moves the robot in a given direction with specified steps."""
    global STOP_MOVE_SEQUENCE

    from mini.apis.api_action import MoveRobot
    block: MoveRobot = MoveRobot(True, direction, step)
    resultType, response = await block.execute()
    
    logging.info(f'Move result: {response}')

    if resultType == MiniApiResultType.Success and response.isSuccess:
        await asyncio.sleep(1)  # Ensure movement completes before the next action
        return True
    return False

# Function to execute the movement sequence
async def move_sequence():
    """Executes the predefined movement sequence but stops if an obstacle is detected."""
    global STOP_MOVE_SEQUENCE
    STOP_MOVE_SEQUENCE = False  # Reset the flag before starting

    if await move_robot(MoveRobotDirection.FORWARD, 9) and not STOP_MOVE_SEQUENCE:
        if await move_robot(MoveRobotDirection.BACKWARD, 4):
            if await move_robot(MoveRobotDirection.RIGHTWARD, 6) and not STOP_MOVE_SEQUENCE:
                if await move_robot(MoveRobotDirection.FORWARD, 5) and not STOP_MOVE_SEQUENCE:
                    await play_tts("Finished cleaning, returning to home position")

# Function to monitor infrared distance (Overrides movement if an obstacle is detected)
async def observe_infrared_distance():
    """Stops the robot if an obstacle is detected, moves backward after a delay, and resumes movement after clearance."""
    global STOP_MOVE_SEQUENCE
    observer: ObserveInfraredDistance = ObserveInfraredDistance()

    async def handler(msg: ObserveInfraredDistanceResponse):
        global STOP_MOVE_SEQUENCE
        print(f"Distance = {msg.distance}")

        if msg.distance < 150:  # If obstacle is detected within 150 units
            observer.stop()  # Stop sensor to prevent continuous triggering
            STOP_MOVE_SEQUENCE = True  # Stop movement sequence
            await play_tts("Obstacle detected, stopping movement.")

            # Stop for 2 seconds before moving back
            await asyncio.sleep(2)

            # Move backward to avoid obstacle (increase distance to 5)
            await move_robot(MoveRobotDirection.BACKWARD, 5)

            # Wait for 2 seconds after moving back to stabilize
            await asyncio.sleep(2)

            STOP_MOVE_SEQUENCE = False  # Resume movement sequence
            observer.start()  # Restart distance observation
            await move_sequence()  # Continue move sequence from where it left off

    observer.set_handler(lambda msg: asyncio.create_task(handler(msg)))
    observer.start()
    await asyncio.sleep(0)

# Function for speech recognition (Runs first!)
async def observe_speech():
    """Handles voice commands: 'please clean.' and 'finish.'."""
    observer = ObserveSpeechRecognise()

    async def handler(msg: SpeechRecogniseResponse):
        recognized_text = str(msg.text).strip().lower()
        print(f'Raw Speech Recognition Output: "{recognized_text}"')

        if recognized_text == "hello.":
            print("Recognized 'please clean', starting movement sequence...")
            await play_tts("Starting cleaning process")
            observer.stop()  # Stop listening after "please clean."
            await observe_infrared_distance()  # Start infrared detection
            await move_sequence()  # Start movement sequence

        elif recognized_text == "finish.":
            print("Recognized 'finish', stopping the program...")
            await play_tts("Shutting down.")
            observer.stop()
            await shutdown()
            return  # Exit the function

    observer.set_handler(lambda msg: asyncio.create_task(handler(msg)))
    observer.start()

'''
Connection Initialization Code (Computer to AlphaMini)
'''
# Function for finding the device
async def get_device_by_name():
    result: WiFiDevice = await Mini.get_device_by_name("00345", 10)  # Enter AlphaMini-Robot ID
    print(f"Device Found: {result}")
    return result

# Function for binding device with computer
async def connection(dev: WiFiDevice) -> bool:
    return await Mini.connect(dev)

# Function for starting the program loop
async def start_run_program():
    await Mini.enter_program()

# Function for shutting down the program
async def shutdown():
    await Mini.quit_program()
    await Mini.release()

# Main Function
async def main():
    device: WiFiDevice = await get_device_by_name()
    if device:
        await connection(device)
        await start_run_program()

        # Run speech recognition first
        await observe_speech()

        # Keep program running until "finish" is detected
        while True:
            await asyncio.sleep(1)  # Prevents the program from exiting immediately

if __name__ == '__main__':
    asyncio.run(main())
