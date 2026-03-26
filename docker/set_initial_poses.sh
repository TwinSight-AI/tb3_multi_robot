#!/bin/bash
set -e

source /opt/ros/${ROS_DISTRO}/setup.bash
source /opt/ros2_ws/install/setup.bash

echo "[init] Waiting for Nav2 lifecycle nodes to be active..."

# Wait until both amcl nodes are available (indicates Nav2 is up)
until ros2 node list 2>/dev/null | grep -q "/tb1/amcl" && \
      ros2 node list 2>/dev/null | grep -q "/tb3/amcl"; do
  echo "[init] Nav2 not ready yet, retrying in 5s..."
  sleep 5
done

echo "[init] Nav2 is up. Publishing initial poses..."

# TB1
ros2 topic pub --once /tb1/initialpose geometry_msgs/msg/PoseWithCovarianceStamped "header:
  frame_id: 'map'
pose:
  pose:
    position: {x: -1.500653720729433, y: -0.5000000060919606, z: 0.0}
    orientation: {x: 0.0, y: 0.0, z: -1.9562638e-06, w: 0.99999595}
  covariance: [0.25, 0, 0, 0, 0, 0,
               0, 0.25, 0, 0, 0, 0,
               0, 0, 0.0001, 0, 0, 0,
               0, 0, 0, 0.0001, 0, 0,
               0, 0, 0, 0, 0.0001, 0,
               0, 0, 0, 0, 0, 0.06853892]"

echo "[init] TB1 initial pose set."

# TB3
ros2 topic pub --once /tb3/initialpose geometry_msgs/msg/PoseWithCovarianceStamped "header:
  frame_id: 'map'
pose:
  pose:
    position: {x: 1.499346279270567, y: -0.50000000609196049, z: 0.0}
    orientation: {x: 0.0, y: 0.0, z: -1.9562638e-06, w: 0.99999595}
  covariance: [0.25, 0, 0, 0, 0, 0,
               0, 0.25, 0, 0, 0, 0,
               0, 0, 0.0001, 0, 0, 0,
               0, 0, 0, 0.0001, 0, 0,
               0, 0, 0, 0, 0.0001, 0,
               0, 0, 0, 0, 0, 0.06853892]"

echo "[init] TB3 initial pose set."
echo "[init] Done. All initial poses published."
