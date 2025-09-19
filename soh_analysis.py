import sys
import json
import time
import tracemalloc
from math import floor
from pathlib import Path
from typing import Dict, List


# --------- Constants & thresholds assumptions ----------
# Needed event states "drive, charge, rest".
CHARGE_EVENT = "charge"

# exclude samples that didn't exceed a certain percentage on calculation for the data to be accurate.
MIN_DELTA_SOC = 5.0



class BatteryDataProcessor:
    """This class is like a temporary notebook for our data. It holds all the info we need
    while we loop through the logs, so we don't have to use messy global variables or loop over data more than once."""
    def __init__(self, design_capacity_kwh):
        # keep track of the current charge cycle's events.
        self.current_charge: List[Dict[str, float]] = []
        # A flag to know if the battery has hit 100% SoC so we can neglect other records even if event still charging.
        self.reached_full_charge: bool = False
        # A flag to signal that a charge cycle has ended so we can run calculations.
        self.charge_end: bool = False
        # This is where we'll store all the SoH results from each valid charge cycle so we can later calculate average.
        self.charge_results: List[float] = []
        # The battery's original capacity, which we'll need for our SoH calculation.
        self.design_capacity_kwh = design_capacity_kwh

    @staticmethod
    def get_single_charge_result(cumulative_charge, delta_soc, design_capacity_kwh):
        """This function does the actual math for one charge cycle.
        calculation here made based on change on SoC increase percentage and what is the power input taken
        compared to what it could be to reach from 0% to 100%.
        eg: Soc increased by 30% using 40kwh so the estimated capacity = 30*100/40.
        finally we compare estimate to design capacity and get SoH percentage"""

        # Calculate the battery's estimated capacity based on the energy added and the SoC change.
        estimated_capacity = cumulative_charge*100 / delta_soc
        # comparing the estimated capacity to the original design to get the SoH.
        charge_soh = estimated_capacity/design_capacity_kwh * 100
        return charge_soh

    def handle_battery_charging_event(self, event_log):
        """This method gets called for every charging log entry.
        It's the core of the processor eventually what we are doing here is accumlating the data we need
        while preserving the values and tracking new charge cycles to get averages using flags to reset."""

        # adding  the new data point to our current charge cycle log only if we haven't hit 100% yet.
        if not self.reached_full_charge:
            self.current_charge.append(
                {
                    "soc": event_log['soc'],
                    "energy_in_kwh": event_log['energy_in_kwh']
                }
            )

        # update full charge flag value to avoid adding more data for this charge while it won't be realistic.
        self.reached_full_charge = floor(event_log['soc']) == 100

        # when charge_end flag is raised this means it's the last event in this single charge cycle so we get results.
        if self.charge_end:
            last_log = self.current_charge
            
            # We grab the start and end SoC directly and sum up all the energy added.
            start_soc = last_log[0]['soc']
            end_soc = last_log[-1]['soc']
            # The total energy from this charge cycle.
            cumulative_charge = sum([charge['energy_in_kwh'] for charge in last_log])
            # The total change in SoC for this cycle.
            delta_soc = end_soc - start_soc

            # We only calculate and store the result if the charge cycle was long enough to be meaningful.
            if delta_soc > MIN_DELTA_SOC:
                charge_result = self.get_single_charge_result(cumulative_charge, delta_soc, self.design_capacity_kwh)
                self.charge_results.append(charge_result)

            # We're done with this charge cycle, so we reset our flags and clear our log to get ready for the next one.
            self.charge_end = False
            self.reached_full_charge = False
            self.current_charge = []
            print("End Of charge")


    def get_average_soh(self):
        """This method calculates the final average SoH from all the charge cycles results we processed."""
        if self.charge_results:
            average = sum(self.charge_results) / len(self.charge_results)
            return average
        return None


def handle_battery_data_extraction(log_data):
    """This is the main function that coordinates everything. It loops through the logs
    and hands off the data to our processor class."""
    vehicle_data = log_data["vehicle"]
    logs = log_data.get("logs")
    if not logs:
        # If there are no logs to process, we return early.
        return {
            "soh": None,
            "cd_count": "",
            "anomalies": ""
        }

    processor = BatteryDataProcessor(vehicle_data["design_capacity_kwh"])

    for i, log in enumerate(logs):
        # We check the `event` to see what kind of data we're looking at.
        if log["event"] == CHARGE_EVENT:
            # We set this flag to True if the next log isn't a charge event, or if it's the last log in the file.
            processor.charge_end = (i+1 < len(logs) and logs[i+1]["event"] != CHARGE_EVENT) or i+1 == len(logs)
            processor.handle_battery_charging_event(log)

    # First: Battery State of Health (in %).
    soh = processor.get_average_soh()

    # TODO Second: Count of charge/discharge cycles
    # TODO Third: flagged anomalies (voltage imbalance, cell overheating)

    battery_data = {
        "vehicle_info": {
            "vin": vehicle_data["vin"],
            "make": vehicle_data["make"],
            "model": vehicle_data["model"],
            "year": vehicle_data["year"],
            "design_capacity_kwh": vehicle_data["design_capacity_kwh"]
        },
        "soh": soh,
        "cd_count": "",
        "anomalies": ""
    }
    return battery_data


def load_json_log_file(file_path: str) -> tuple[dict, str]:
    """
    Reads a JSON log file and returns its contents as a python dictionary.
    """
    data = {}
    error = ""

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    with path.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            error = str(e)

    return data, error


def main():
    if len(sys.argv) < 2:
        print("""Missing Json File path
        Usage: python soh_analysis.py <path-to-json>""")
    else:
        # We'll use this to measure how long the whole process takes.
        start_time = time.perf_counter()

        # Start tracking memory usage before we do anything.
        tracemalloc.start()

        received_file_path = sys.argv[1]
        result, e = load_json_log_file(received_file_path)

        # Make sure we have some data before we start processing.
        if result:
            # We count the number of log entries to give a sense of the scale of the file.
            num_records = len(result.get("logs") or result.get("samples", []))

            # The main analysis function call.
            battery_data =  handle_battery_data_extraction(result)
            print("Battery Data")
            print(json.dumps(battery_data, indent=4))

            # Now we can calculate and print our performance metrics.
            end_time = time.perf_counter()
            elapsed_time = end_time - start_time

            # Get the current and peak memory usage from the tracker.
            current, peak = tracemalloc.get_traced_memory()

            # Stop tracking to free up resources.
            tracemalloc.stop()

            print("\n--- Performance Metrics ---")
            print(f"Time Taken: {elapsed_time:.4f} seconds")
            print(f"Number of Records Processed: {num_records}")
            print(f"Current Memory Usage: {current / 10**6:.2f} MB")
            print(f"Peak Memory Usage: {peak / 10**6:.2f} MB")
        else:
            print(f"Error: {e}" if e else "No Data To Process")


if __name__ == "__main__":
    main()