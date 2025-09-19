import sys
import json
import time
import tracemalloc
from math import floor
from pathlib import Path
from typing import Dict , List , Optional
from build_report import build_reports


# --------- Constants & thresholds assumptions ----------
# Needed event states "drive, charge, rest".
CHARGE_EVENT = "charge"
DRIVE_EVENT = "drive"
REST_EVENT = "rest"

# exclude samples that didn't exceed a certain percentage on calculation for the data to be accurate.
MIN_DELTA_SOC = 5.0
# max voltage per cell
MAX_CELL_VOLTAGE = 4.2
# min voltage per cell
MIN_CELL_VOLTAGE = 2.5
# max cell voltage difference for EV at rest.
IMBALANCE_MV_AT_REST = 30.0
# max cell voltage difference for EV under load.
IMBALANCE_MV_UNDER_LOAD = 60.0
# We use this to decide if the battery is "at rest" or "under load. so we can detect voltage anomalies"
C_RATE_LOAD_THRESHOLD = 0.1
# max cell temp allowed
MAX_CELL_TEMP_C = 55.0
# min cell temp allowed
MIN_CELL_TEMP_C = 0.0
# max temp differences between cells
MAX_CELLS_TEMP_DIFFERENCE = 5.0


class BatteryDataProcessor:
    """This class is like a temporary notebook for our data. It holds all the info we need
    while we loop through the logs, so we don't have to use messy global variables or loop over data more than once."""
    def __init__(self, design_capacity_kwh, nominal_pack_voltage):
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
        # The battery's nominal_pack_voltage, which we'll need for our voltage anomalies calculation.
        self.nominal_pack_voltage = nominal_pack_voltage
        # For our cycle counting, we need to track the last SoC seen and the cumulative total change.
        self.last_soc: Optional[float] = None
        self.cumulative_soc_delta: float = 0.0
        self.cumulative_charge_soc_delta: float = 0.0
        # To get all voltage anomalies we need to store and aggregate detected ones
        self.voltage_difference_anomalies: List[dict] = []
        self.voltage_range_anomalies: List[dict] = []
        # To get all temperature anomalies we need to store and aggregate detected ones
        self.temperature_difference_anomalies: List[dict] = []
        self.temperature_range_anomalies: List[dict] = []

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
            delta_soc = abs(end_soc - start_soc)

            # We only calculate and store the result if the charge cycle was long enough to be meaningful.
            if delta_soc > MIN_DELTA_SOC:
                charge_result = self.get_single_charge_result(cumulative_charge, delta_soc, self.design_capacity_kwh)
                self.charge_results.append(charge_result)

            # We're done with this charge cycle, so we reset our flags and clear our log to get ready for the next one.
            self.charge_end = False
            self.reached_full_charge = False
            self.current_charge = []

    def get_average_soh(self):
        """This method calculates the final average SoH from all the charge cycles results we processed."""
        if self.charge_results:
            average = sum(self.charge_results) / len(self.charge_results)
            return round(average, 2)
        return None

    def handle_overall_soc_changes(self, current_soc, event):
        """This method calculates overall and event based SoC delta to calculate cycle of charge/discharge"""

        if self.last_soc is None:
            self.last_soc = current_soc
            return

        # first overall cumulative SoC
        current_soc_delta = abs(current_soc - self.last_soc)
        self.cumulative_soc_delta += current_soc_delta
        self.last_soc = current_soc
        # Second get charge only so later we can calculate discharge
        if event == CHARGE_EVENT:
            self.cumulative_charge_soc_delta += current_soc_delta


    def get_average_charge_discharge_cycles_data(self):
        """This method the actual count for the charge discharge cycles overall & event based through
        a full cycle (100%)"""
        overall_cycles = round(self.cumulative_soc_delta/100, 2)
        charge_cycles = round(self.cumulative_charge_soc_delta/100, 2)
        discharge_cycles = round((overall_cycles- charge_cycles), 2)
        return {
            "overall_cycles": overall_cycles,
            "charge_cycles": charge_cycles,
            "discharge_cycles": discharge_cycles
        }

    def get_voltage_anomalies(self, log):
        """ This method gets voltage anomalies from all the charge cycles results we processed.
        it studies two aspects 1- range limits, 2- difference limit"""
        voltage_range_anomalies = []
        voltage_difference_anomalies = []
        cell_voltages = log['cell_voltages']
        min_voltage = min(cell_voltages)
        max_voltage = max(cell_voltages)
        voltage_difference_mv = (max_voltage - min_voltage) * 1000

        # detect anomalies that has their voltage out of range
        if max_voltage > MAX_CELL_VOLTAGE:
            voltage_range_anomalies.append({
                "min_voltage": min_voltage,
                "max_voltage": max_voltage,
                "max_allowed_voltage": MAX_CELL_VOLTAGE,
                "min_allowed_voltage": MIN_CELL_VOLTAGE,
                "comment": "Cell voltage too high",
                "timestamp": log["ts"]
            })
        if min_voltage < MIN_CELL_VOLTAGE:
            voltage_range_anomalies.append({
                "min_voltage": min_voltage,
                "max_voltage": max_voltage,
                "max_allowed_voltage": MAX_CELL_VOLTAGE,
                "min_allowed_voltage": MIN_CELL_VOLTAGE,
                "comment": "Cell voltage too low",
                "timestamp": log["ts"]
            })

        # calculate nominal capacity in order to calculate current c_rate
        nominal_capacity = self.design_capacity_kwh * 1000 / self.nominal_pack_voltage

        # now calculating the current c_rate to decide which threshold to use at rest or under load
        current_c_rate = abs(log["pack_current"])/nominal_capacity

        # pick which threshold we should use based on current c_rate
        if current_c_rate > C_RATE_LOAD_THRESHOLD:
            threshold = IMBALANCE_MV_UNDER_LOAD
            comment = "Cell voltage difference exceeds threshold under load"
        else:
            threshold = IMBALANCE_MV_AT_REST
            comment = "Cell voltage difference exceeds threshold at rest"
        if voltage_difference_mv > threshold:
            voltage_difference_anomalies.append({
                "voltage_difference": voltage_difference_mv,
                "comment": comment,
                "threshold": threshold,
                "timestamp": log["ts"]
            })

        return {
            **(
                {"voltage_difference_anomalies": voltage_difference_anomalies}
                if any(voltage_difference_anomalies)
                else {}
            ),
            **(
                {"voltage_range_anomalies": voltage_range_anomalies}
                if any(voltage_range_anomalies)
                else {}
            )
        }

    @staticmethod
    def get_temperature_anomalies(log):
        """
        This method gets temperature anomalies from all the charge cycles results we processed.
        It studies two aspects 1- range limits, 2- difference limit
        """
        temperature_range_anomalies = []
        temperature_difference_anomalies = []
        cell_temperatures = log["cell_temps_c"]
        max_cell_temperature = max(cell_temperatures)
        min_cell_temperature = min(cell_temperatures)
        cells_temperature_difference = max_cell_temperature - min_cell_temperature

        if max_cell_temperature > MAX_CELL_TEMP_C:
            temperature_range_anomalies.append({
                "min_cell_temperature": min_cell_temperature,
                "max_cell_temperature": max_cell_temperature,
                "min_allowed_cell_temperature": MIN_CELL_TEMP_C,
                "max_allowed_cell_temperature": MAX_CELL_TEMP_C,
                "comment": "Cell temperature too high",
                "timestamp": log["ts"]
            })

        if min_cell_temperature < MIN_CELL_TEMP_C:
            temperature_range_anomalies.append({
                "min_cell_temperature": min_cell_temperature,
                "max_cell_temperature": max_cell_temperature,
                "min_allowed_cell_temperature": MIN_CELL_TEMP_C,
                "max_allowed_cell_temperature": MAX_CELL_TEMP_C,
                "comment": "Cell temperature too low",
                "timestamp": log["ts"]
            })

        if cells_temperature_difference > MAX_CELLS_TEMP_DIFFERENCE:
            temperature_difference_anomalies.append({
                "cells_temperature_difference": cells_temperature_difference,
                "max_cells_temperature_difference": MAX_CELLS_TEMP_DIFFERENCE,
                "comment": "Cell temperature difference too high",
                "timestamp": log["ts"]
            })

        return {
            **(
                {"temperature_range_anomalies": temperature_range_anomalies}
                if any(temperature_range_anomalies)
                else {}
            ),
            **(
                {"temperature_difference_anomalies": temperature_difference_anomalies}
                if any(temperature_difference_anomalies)
                else {}
            )
        }

    def handle_anomalies_detection(self, log):
        voltage_anomalies = self.get_voltage_anomalies(log)

        if voltage_anomalies:
            (voltage_anomalies.get("voltage_difference_anomalies") and
             self.voltage_difference_anomalies.extend(voltage_anomalies["voltage_difference_anomalies"]))

            (voltage_anomalies.get("voltage_range_anomalies") and
             self.voltage_range_anomalies.extend(voltage_anomalies["voltage_range_anomalies"]))

        temperature_anomalies = self.get_temperature_anomalies(log)

        if temperature_anomalies:
            (temperature_anomalies.get("temperature_difference_anomalies") and
             self.temperature_difference_anomalies.extend(temperature_anomalies["temperature_difference_anomalies"]))
            (temperature_anomalies.get("temperature_range_anomalies") and
             self.temperature_range_anomalies.extend(temperature_anomalies["temperature_range_anomalies"]))

    def get_detected_anomalies(self):
        return {
            "voltage": {
                "voltage_range_anomalies": self.voltage_range_anomalies,
                "voltage_difference_anomalies": self.voltage_difference_anomalies
            },
            "temperature": {
                "temperature_range_anomalies": self.temperature_range_anomalies,
                "temperature_difference_anomalies": self.temperature_difference_anomalies
            }
        }

def handle_battery_data_extraction(log_data):
    """This is the main function that coordinates everything. It loops through the logs
    and hands off the data to our processor class."""
    vehicle_data = log_data["vehicle"]
    logs = log_data.get("logs")
    if not logs:
        # If there are no logs to process, we return early.
        return {}

    processor = BatteryDataProcessor(vehicle_data["design_capacity_kwh"], vehicle_data["nominal_pack_voltage"])

    for i, log in enumerate(logs):
        # handle overall SoC changes
        event = log["event"]
        processor.handle_overall_soc_changes(log["soc"], event)

        # handle anomalies detection
        processor.handle_anomalies_detection(log)

        # We check the `event` to see what kind of data we're looking at.
        if event == CHARGE_EVENT:
            # We set this flag to True if the next log isn't a charge event, or if it's the last log in the file.
            processor.charge_end = (i+1 < len(logs) and logs[i+1]["event"] != CHARGE_EVENT) or i+1 == len(logs)
            processor.handle_battery_charging_event(log)

    # First: Battery State of Health (in %).
    soh = processor.get_average_soh()

    # Second: Count of charge/discharge cycles
    cdc_data = processor.get_average_charge_discharge_cycles_data()

    # Third: flagged anomalies (voltage imbalance, cell overheating)
    anomalies = processor.get_detected_anomalies()
    battery_data = {
        "vehicle_info": {
            "vin": vehicle_data["vin"],
            "make": vehicle_data["make"],
            "model": vehicle_data["model"],
            "year": vehicle_data["year"],
            "design_capacity_kwh": vehicle_data["design_capacity_kwh"]
        },
        "soh": soh,
        "cdc_data": cdc_data,
        "anomalies": anomalies
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
            build_reports(battery_data)

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