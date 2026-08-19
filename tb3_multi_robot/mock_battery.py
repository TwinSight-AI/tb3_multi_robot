#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState

FULL_VOLTAGE = 12.6
EMPTY_VOLTAGE = 11.1
MIN_PERCENTAGE = 0.2


class MockBattery(Node):
    """Publish a fake but slowly-changing BatteryState for simulation."""

    def __init__(self):
        super().__init__('mock_battery')

        self.declare_parameter('battery_topic', '/battery_state')
        self.declare_parameter('publish_rate_hz', 1.0)
        self.declare_parameter('drain_per_publish', 0.001)

        battery_topic = self.get_parameter('battery_topic').value
        publish_rate_hz = self.get_parameter('publish_rate_hz').value
        self.drain_per_publish = self.get_parameter('drain_per_publish').value

        self.percentage = 1.0
        self.battery_pub = self.create_publisher(BatteryState, battery_topic, 10)
        self.timer = self.create_timer(1.0 / publish_rate_hz, self._publish_battery_state)

        self.get_logger().info(f'Mock battery publishing on {battery_topic}')

    def _publish_battery_state(self) -> None:
        self.percentage -= self.drain_per_publish
        if self.percentage < MIN_PERCENTAGE:
            self.percentage = 1.0

        msg = BatteryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.voltage = EMPTY_VOLTAGE + self.percentage * (FULL_VOLTAGE - EMPTY_VOLTAGE)
        msg.current = -0.5
        msg.percentage = self.percentage
        msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        msg.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_GOOD
        msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LIPO
        msg.present = True

        self.battery_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MockBattery()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
