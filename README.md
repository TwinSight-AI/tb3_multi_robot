# Multi-TurtleBot3 Simulation: ROS 2 Jazzy · Gazebo Harmonic · Nav2

This repository simulates several TurtleBot3 robots in one Gazebo Harmonic world. Each robot gets its own ROS 2 namespace (`/tb1`, `/tb2`, …), its own TF tree, its own Nav2 stack and RViz window, and a mock battery.

It is a fork of [arshadlab/tb3_multi_robot](https://github.com/arshadlab/tb3_multi_robot). Use the **`main`** branch. The simulation runs standalone, with no extra repositories needed. The `humble` and `foxy` branches contain unchanged upstream code and are not covered here.

---

## Contents

1. [How it fits together](#1-how-it-fits-together)
2. [Repository layout](#2-repository-layout)
3. [Choose how to run it](#3-choose-how-to-run-it)
4. [Get the code](#4-get-the-code)
5. [Configure before you build](#5-configure-before-you-build)
6. [Run with Docker Compose](#6-run-with-docker-compose)
7. [Run natively on Ubuntu 24.04](#7-run-natively-on-ubuntu-2404)
8. [Check that it works](#8-check-that-it-works)
9. [Operating the robots](#9-operating-the-robots)
10. [Developing against a local checkout inside Docker](#10-developing-against-a-local-checkout-inside-docker)
11. [Troubleshooting and performance](#11-troubleshooting-and-performance)
12. [FAQ: why `/tf` is remapped](#12-faq-why-tf-is-remapped)
13. [Optional: running with the TwinSight robot_adapter](#13-optional-running-with-the-twinsight-robot_adapter)
14. [Credits](#14-credits)
15. [Appendix: topics per robot with the Nav2 backend](#appendix-topics-per-robot-with-the-nav2-backend)

---

## 1. How it fits together

The simulation is started in two steps, always in this order:

| Step | Launch file | Starts once | Starts for every enabled robot |
|---|---|---|---|
| **1. World** | `tb3_world.launch.py` | Gazebo server and GUI, `/clock` bridge | Robot spawned in Gazebo as `<name>_<model>` (e.g. `tb1_burger`), `robot_state_publisher`, `ros_gz_bridge`, plus a camera bridge if the model is `waffle` |
| **2a. Nav2 backend** | `tb3_nav2.launch.py` | — | Nav2 bringup (map server, AMCL, planner, controller, behaviors, BT navigator, collision monitor, docking…), an RViz window, `mock_battery` |
| **2b. Simple driver** (instead of 2a) | `drive.launch.py` | — | `turtlebot3_drive`, a basic obstacle-avoiding wander node |

Before you start:

- **[`config/robots.yaml`](config/robots.yaml) controls everything.** It sets which robots exist, their names and their start poses, and every launch file reads it.
- **The robot model** comes from the `TURTLEBOT3_MODEL` environment variable. The default is `burger`.
- **Battery data only exists in Nav2 mode.** `mock_battery` is started by `tb3_nav2.launch.py`. If only step 1 is running, or step 2b, nothing publishes `/<ns>/battery_state`.
- **Run either 2a or 2b, never both.** Both publish to `/<ns>/cmd_vel`.

---

## 2. Repository layout

```
tb3_multi_robot/
├── config/robots.yaml           # robot list, names, start poses, enabled flags  ← edit this
├── launch/
│   ├── tb3_world.launch.py      # step 1: Gazebo + per-robot spawn/RSP/bridge
│   ├── tb3_nav2.launch.py       # step 2a: per-robot Nav2 + RViz + mock_battery
│   └── drive.launch.py          # step 2b: per-robot simple driver
├── params/
│   ├── <model>_bridge.yaml      # ros_gz_bridge topic templates (namespaced at launch)
│   └── <model>_nav2_params.yaml # Nav2 params template (namespaced + initial pose at launch)
├── map/map.yaml, map.pgm        # map used by every robot's map_server
├── models/, urdf/, worlds/      # TurtleBot3 models and the tb3_world world
├── rviz/tb3_navigation2.rviz    # RViz template (title gets the robot name)
├── multi_robot_scripts/         # launch helpers (namespacing) + turtlebot3_drive node
├── tb3_multi_robot/mock_battery.py
├── twin_configs/tbX/            # per-robot map copies (not used by any launch file)
└── docker/
    ├── Dockerfile
    ├── docker-compose.yaml                  # standalone stack
    ├── docker-compose.robot-adapter.yaml    # optional override, see section 13
    └── entrypoint.sh
```

At launch time, the bridge YAML, Nav2 params and RViz config are generated for each robot under `/tmp`, for example `/tmp/tb1_bridge.yaml`, `/tmp/tb1_nav2_params.yaml` and `/tmp/tb1_rviz_config.rviz`. Look there to see exactly what a robot was started with.

---

## 3. Choose how to run it

| | **Docker Compose** (section 6) | **Native** (section 7) |
|---|---|---|
| Host OS | Any Linux with Docker and an X11 display | Ubuntu 24.04 with an X11 display |
| GPU | NVIDIA GPU + NVIDIA Container Toolkit (the compose file requests `gpus: all`) | Any GPU that runs Gazebo Harmonic |
| ROS on host | Not needed | ROS 2 Jazzy |
| Best for | Running the stack as-is | Developing and debugging nodes |

Both paths start the same way: get the code (section 4), then configure it (section 5).

---

## 4. Get the code

```bash
mkdir -p ~/multirobot_ws/src
cd ~/multirobot_ws/src
git clone https://github.com/TwinSight-AI/tb3_multi_robot.git -b main
```

The rest of this README assumes the workspace is at `~/multirobot_ws`. Adjust the paths if you put it elsewhere.

---

## 5. Configure before you build

The build copies `robots.yaml` into the install space (native) or the Docker image (Compose). Edit it before building, and rebuild after every change.

### 5.1 Robots: `config/robots.yaml`

```yaml
robots:
  - name: tb1          # namespace (/tb1) and Gazebo entity prefix (tb1_burger)
    x_pose: "-1.5"     # spawn position in Gazebo, also AMCL's initial pose
    y_pose: "-0.5"
    z_pose: 0.01       # used only for AMCL's initial pose (spawn height is fixed to 0.01)
    yaw: 0.0           # used only for AMCL's initial pose (see note below)
    enabled: true      # false = robot is not spawned and gets no Nav2 stack
  - name: tb2
    ...
```

By default **all four robots (tb1–tb4) are enabled**. They spawn at (-1.5, -0.5), (-1.5, 0.5), (1.5, -0.5) and (1.5, 0.5).

> ⚠️ **Keep `yaw: 0.0`.** The Gazebo spawner ignores yaw, so every robot spawns facing +X. A non-zero yaw only reaches AMCL, so that robot would start mislocalized.

Four robots with Nav2 is a heavy load. If your machine struggles, disable some of them (see section 11).

### 5.2 Robot model: `TURTLEBOT3_MODEL`

| Value | Status |
|---|---|
| `burger` (default) | Supported. Lidar + IMU, no camera. |
| `waffle` | Supported. Adds a camera: `/<ns>/camera/image_raw` and `/<ns>/camera/camera_info`. |
| `waffle_pi`, `burger_cam` | **Not supported.** Some of their files exist, but the Gazebo models and parameter files are incomplete. |

For a native run, set it in the shell before launching, for example `export TURTLEBOT3_MODEL=waffle`. Use the same value for step 1 and step 2.

---

## 6. Run with Docker Compose

`docker/docker-compose.yaml` builds one image from this repository and runs two containers from it:

- **`tb3-world`** runs `ros2 launch tb3_multi_robot tb3_world.launch.py` and opens the Gazebo window.
- **`tb3-nav2`** runs `ros2 launch tb3_multi_robot tb3_nav2.launch.py` and opens one RViz window per robot. It starts after `tb3-world`.

### 6.1 Allow the containers to open windows

```bash
xhost +local:docker
```

### 6.2 Build and start

```bash
cd ~/multirobot_ws/src/tb3_multi_robot/docker
docker compose up --build
```

The image contains a copy of the repository, not your live files. Run `up --build` again after any change to `robots.yaml` or the code.

To stop, press `Ctrl+C`, then run `docker compose down`.

### 6.3 Open a shell in a running container

`docker exec` skips the entrypoint, so source the environment yourself:

```bash
docker exec -it tb3-world bash -c "source /opt/ros/jazzy/setup.bash && source /opt/ros2_ws/install/setup.bash && exec bash"
```

Then continue with section 8.

---

## 7. Run natively on Ubuntu 24.04

### 7.1 Install ROS 2 Jazzy and the required packages

Install ROS 2 Jazzy by following the [official guide](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html). Then install the packages this repo needs:

```bash
sudo apt update && sudo apt install -y \
  ros-jazzy-desktop \
  ros-jazzy-ros-gz \
  ros-jazzy-navigation2 \
  ros-jazzy-nav2-bringup \
  ros-jazzy-rmw-cyclonedds-cpp \
  ros-jazzy-tf-transformations \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-vcstool \
  git
```

`ros-jazzy-ros-gz` brings in Gazebo Harmonic. The `turtlebot3_drive` node needs `ros-jazzy-tf-transformations`.

### 7.2 Configure DDS (CycloneDDS)

Several robots with full Nav2 stacks create more DDS participants than CycloneDDS allows by default. Create `~/cyclonedds.xml`:

```xml
<CycloneDDS>
  <Discovery>
    <ParticipantIndex>auto</ParticipantIndex>
    <MaxAutoParticipantIndex>100</MaxAutoParticipantIndex>
  </Discovery>
</CycloneDDS>
```

Add both lines to `~/.bashrc`. The first one is essential: without it, ROS 2 uses Fast DDS and ignores the file above.

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=$HOME/cyclonedds.xml
```

### 7.3 Install dependencies and build

```bash
cd ~/multirobot_ws
source /opt/ros/jazzy/setup.bash

sudo rosdep init        # only once per machine; skip if it says it is already initialized
rosdep update
rosdep install --from-paths src --ignore-src -r -y

colcon build --symlink-install
source install/setup.bash
```

`rosdep` may report a few keys it cannot resolve, such as `gazebo_ros_pkgs`, which belongs to Gazebo Classic. This is expected. The `-r` flag continues past them, and the packages from 7.1 cover what is actually used.

### 7.4 Launch

Source the environment in every new terminal before running anything:

```bash
source /opt/ros/jazzy/setup.bash
source ~/multirobot_ws/install/setup.bash
```

**Terminal 1: world and robots**

```bash
ros2 launch tb3_multi_robot tb3_world.launch.py
```

Wait until the Gazebo window shows all robots.

**Terminal 2: Nav2 backend**

```bash
ros2 launch tb3_multi_robot tb3_nav2.launch.py
```

One RViz window opens per robot, with the panel titled `Displays (tb1)`, `Displays (tb2)`, and so on. Each robot is already localized at its spawn pose (see 9.2).

Optional `tb3_nav2.launch.py` arguments: `map:=<path to map.yaml>`, `params_file:=<path>`, `use_sim_time:=true|false`.

> **The first launch needs internet access.** The world downloads *Ground Plane* and *Sun* from Gazebo Fuel and caches them in `~/.gz/fuel`. Do not clone `osrf/gazebo_models` into `~/.gazebo/models`, as the upstream README suggests. That folder is only used by Gazebo Classic.

---

## 8. Check that it works

Run these from a sourced terminal (native) or a container shell (section 6.3):

```bash
ros2 topic list | grep '^/tb1/'            # per-robot topics (full list in the Appendix)
ros2 topic hz /tb1/scan                    # lidar is streaming
ros2 topic echo /tb1/odom --once           # odometry from Gazebo
ros2 topic echo /tb1/amcl_pose --once      # AMCL is localized
ros2 topic echo /tb1/battery_state --once  # mock battery (Nav2 mode only)
```

Then send a navigation goal (9.1) and watch the robot move in Gazebo and RViz.

---

## 9. Operating the robots

### 9.1 Send a navigation goal

**From RViz:** in that robot's RViz window, click **Nav2 Goal**, then drag on the map.

**From the command line** (replace `tb1` with any robot name):

```bash
ros2 action send_goal /tb1/navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: map}, pose: {position: {x: 2.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}}"
```

The Appendix lists the other Nav2 actions available for each robot, such as waypoints, spin, backup and docking.

### 9.2 Initial pose (localization)

`tb3_nav2.launch.py` seeds AMCL with each robot's `x_pose`, `y_pose`, `z_pose` and `yaw` from `robots.yaml`. These are the same values the robot spawns with, so **no manual "2D Pose Estimate" is needed at startup**.

You only need to re-localize when a robot's real position no longer matches its estimate, for example after you move it in Gazebo:

- **RViz:** in that robot's window, click **2D Pose Estimate**, then click and drag at the robot's real position and heading.
- **Command line:** read the robot's real pose from Gazebo, then publish it.

  ```bash
  gz topic -e -t /world/default/pose/info    # look for the entity named tb1_burger (or tb1_waffle)
  ```

  ```bash
  ros2 topic pub --once /tb1/initialpose geometry_msgs/msg/PoseWithCovarianceStamped "
  header: {frame_id: map}
  pose:
    pose:
      position: {x: -1.5, y: -0.5, z: 0.0}
      orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
    covariance: [0.25, 0, 0, 0, 0, 0,
                 0, 0.25, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0.0685]"
  ```

  Change the namespace in the topic name, and the position and orientation (a quaternion), to match the robot.

### 9.3 Driving without Nav2

Run this **instead of** `tb3_nav2.launch.py`, after `tb3_world.launch.py` is up:

```bash
# all enabled robots
ros2 launch tb3_multi_robot drive.launch.py

# or a single robot
ros2 run tb3_multi_robot turtlebot3_drive --ros-args -r __ns:=/tb1 -p use_sim_time:=true
```

This is a Python port of the upstream TurtleBot3 `turtlebot3_drive` node. It publishes `geometry_msgs/TwistStamped`, which is the type the Gazebo Harmonic bridge expects.

This mode has no battery data. To get it, start a mock battery for each robot:

```bash
ros2 run tb3_multi_robot mock_battery --ros-args -r __ns:=/tb1 -p battery_topic:=battery_state
```

### 9.4 RViz / rqt for a single robot

TF listeners always subscribe to the absolute `/tf` and `/tf_static` topics. When you start a tool inside a robot's namespace, remap them (section 12 explains why):

```bash
rqt   --ros-args -r __ns:=/tb1 -r /tf:=tf -r /tf_static:=tf_static
rviz2 --ros-args -r __ns:=/tb1 -r /tf:=tf -r /tf_static:=tf_static
```

---

## 10. Developing against a local checkout inside Docker

The Compose image holds a **copy** of the repository in `/opt/ros2_ws`. To edit code on the host and build it inside the container, mount your workspace and build there:

```bash
cd ~/multirobot_ws/src/tb3_multi_robot
docker build -t tb3_multi_robot:dev -f docker/Dockerfile .

docker run -it --rm \
  --user $(id -u):$(id -g) \
  --name tb3sim \
  --env DISPLAY=$DISPLAY \
  --env QT_X11_NO_MITSHM=1 \
  --volume /tmp/.X11-unix:/tmp/.X11-unix:rw \
  --volume /dev/dri:/dev/dri \
  --volume $HOME/multirobot_ws:/robot_ws \
  tb3_multi_robot:dev bash
```

Inside the container:

```bash
cd /robot_ws
colcon build              # no --symlink-install if you also build on the host
source install/setup.bash
ros2 launch tb3_multi_robot tb3_world.launch.py
```

Open a second terminal into the same container:

```bash
docker exec -it tb3sim bash -c "source /opt/ros/jazzy/setup.bash && source /robot_ws/install/setup.bash && exec bash"
ros2 launch tb3_multi_robot tb3_nav2.launch.py
```

Build output goes to `/robot_ws`, which is your workspace folder on the host.

---

## 11. Troubleshooting and performance

| Symptom | Likely cause / fix |
|---|---|
| `docker compose up` fails with a GPU / `nvidia` error | The compose file requests `gpus: all`. Install the NVIDIA Container Toolkit. On a machine without an NVIDIA GPU, delete the `gpus: all` line. |
| No window appears from Docker | Run `xhost +local:docker` on the host and check that `DISPLAY` is set. |
| A robot does not localize, or drifts right after start | Its `yaw` in `robots.yaml` is not 0 (section 5.1), or it was moved. Re-localize it (9.2). |
| Nav2 nodes fail to start, or discovery is flaky with many robots | You are hitting the DDS participant limit. Set `RMW_IMPLEMENTATION` and `CYCLONEDDS_URI` (7.2). |
| Gazebo hangs on the first start | It is downloading models from Gazebo Fuel. Check your internet access. |
| Changes to `robots.yaml` have no effect | Rebuild with `colcon build`, or `docker compose up --build`. |

**Performance.** Four robots with full Nav2 stacks are demanding. To lighten the load:

1. **Run fewer robots.** Set `enabled: false` on some of them. Two robots are much lighter than four.
2. **Lower the physics rate** in `worlds/tb3_world.world`. It currently runs at 1000 Hz (`max_step_size` 0.001). For example:
   ```xml
   <real_time_update_rate>100.0</real_time_update_rate>
   <max_step_size>0.01</max_step_size>
   ```
3. **Lower the sensor rates** in the robot model (`models/turtlebot3_<model>/model.sdf`) if you do not need full-rate `/scan`, `/imu` or `/odom`.

---

## 12. FAQ: why `/tf` is remapped

Each robot has its **own TF tree** on `/<ns>/tf` and `/<ns>/tf_static`. That way, frame names such as `odom`, `base_footprint` and `base_link` do not clash between robots. The catch is that the TF listener in `tf2_ros` always subscribes to the **absolute** topics `/tf` and `/tf_static`, even when its node runs inside a namespace. You can check this with `rviz2 --ros-args -r __ns:=/tb1`: it still listens on the global `/tf`.

For this reason, every TF user in this project remaps `/tf → tf` and `/tf_static → tf_static`, which resolve to `/<ns>/tf` and `/<ns>/tf_static`. That covers `robot_state_publisher`, the Gazebo bridge, Nav2 and RViz. Any tool you add needs the same remapping (section 9.4).

---

## 13. Optional: running with the TwinSight robot_adapter

> This section is for teams that have access to the TwinSight `robot_adapter` repository. **Everything above works without it.**

`robot_adapter` sends each robot's telemetry (odometry, IMU, battery) to a TwinSight backend. When it is enabled, `tb3_world.launch.py` starts one `adapter_node` in each robot's namespace. It subscribes to `/<ns>/odom`, `/<ns>/imu` and `/<ns>/battery_state`.

### 13.1 Get the code

Clone `robot_adapter` next to this repository:

```bash
cd ~/multirobot_ws/src
git clone https://github.com/TwinSight-AI/robot_adapter.git -b develop
```

```
~/multirobot_ws/src/
├── tb3_multi_robot/
└── robot_adapter/
```

### 13.2 TwinSight connection settings

`tb3_world.launch.py` reads these environment variables when it starts:

| Variable | Meaning | Default |
|---|---|---|
| `TWINSIGHT_API_BASE_URL` | TwinSight backend URL, shared by all robots | `http://localhost:8001` |
| `<NAME>_ROBOT_ID` | Robot UUID issued by TwinSight, one per robot (`TB1_ROBOT_ID`, `TB2_ROBOT_ID`, …) | empty |
| `<NAME>_ROBOT_SECRET` | Matching robot secret (`TB1_ROBOT_SECRET`, …) | empty |

`<NAME>` is the robot's `name` from `robots.yaml`, in upper case. Create each robot in the TwinSight platform first, then copy its ID and secret.

If no backend is reachable, the simulation and Nav2 still work. The adapters only log connection errors.

### 13.3 Native

Build as in section 7.3. `rosdep` and `colcon` pick up `robot_adapter` automatically. Then start the world with the adapter turned on:

```bash
export TWINSIGHT_API_BASE_URL=http://localhost:8001
export TB1_ROBOT_ID=<uuid>  TB1_ROBOT_SECRET=<secret>
export TB2_ROBOT_ID=<uuid>  TB2_ROBOT_SECRET=<secret>
# ...one pair per enabled robot

ros2 launch tb3_multi_robot tb3_world.launch.py use_robot_adapter:=true
```

Start `tb3_nav2.launch.py` as usual. It also provides the battery data the adapter reads.

### 13.4 Docker Compose

1. Create `docker/.env`:

   ```bash
   cd ~/multirobot_ws/src/tb3_multi_robot/docker
   cat > .env <<'EOF'
   # A backend running on the host is reachable as host.docker.internal
   # ("localhost" inside the container is the container itself).
   TWINSIGHT_API_BASE_URL=http://host.docker.internal:8001
   TB1_ROBOT_ID=
   TB1_ROBOT_SECRET=
   TB2_ROBOT_ID=
   TB2_ROBOT_SECRET=
   TB3_ROBOT_ID=
   TB3_ROBOT_SECRET=
   TB4_ROBOT_ID=
   TB4_ROBOT_SECRET=
   EOF
   ```

2. Start with the override file:

   ```bash
   docker compose -f docker-compose.yaml -f docker-compose.robot-adapter.yaml up --build
   ```

The override needs Docker Compose 2.17 or later. It does three things:

- passes `../../robot_adapter` as an extra build context, so `robot_adapter` is built into the image
- loads `.env` and adds the `host.docker.internal` host entry
- launches the world with `use_robot_adapter:=true`

With plain `docker build`, the equivalent is:

```bash
cd ~/multirobot_ws/src/tb3_multi_robot
docker build -t tb3_multi_robot:latest -f docker/Dockerfile \
  --build-context robot_adapter=../robot_adapter .
```

### 13.5 Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `package 'robot_adapter' not found` | `use_robot_adapter:=true` is set, but `robot_adapter` is not in the workspace or not built (13.1). |
| Adapter logs `Connection refused` | No backend is listening at `TWINSIGHT_API_BASE_URL`. In Docker, use `http://host.docker.internal:<port>`, not `localhost`. |
| `docker compose` fails with `env file ... .env not found` | Create `docker/.env` (13.4). |
| `additional_contexts` is rejected | Your Docker Compose is older than 2.17. Update it, or build with `docker build --build-context ...` as shown above. |

---

## 14. Credits

Based on [arshadlab/tb3_multi_robot](https://github.com/arshadlab/tb3_multi_robot) by Arshad Mehmood. Some configuration and model files come from the TurtleBot3 and Nav2 projects and were adapted for multi-robot use. Credit for those files remains with their original authors and maintainers.

---

## Appendix: topics per robot with the Nav2 backend

These are the topics for one robot (`tb1`) while `tb3_world.launch.py` **and** `tb3_nav2.launch.py` are running with the default `burger` model. Every other robot has the same set under its own namespace (`/tb2/...`, `/tb3/...`). To see the live list:

```bash
ros2 topic list -t | grep -E '^/tb1/'
```

### Sensors and base (Gazebo ↔ ROS bridge)

| Topic | Type | Direction / source |
|---|---|---|
| `/tb1/scan` | `sensor_msgs/msg/LaserScan` | Gazebo → ROS (lidar) |
| `/tb1/imu` | `sensor_msgs/msg/Imu` | Gazebo → ROS |
| `/tb1/odom` | `nav_msgs/msg/Odometry` | Gazebo → ROS (diff-drive odometry) |
| `/tb1/joint_states` | `sensor_msgs/msg/JointState` | Gazebo → ROS (wheel joints) |
| `/tb1/cmd_vel` | `geometry_msgs/msg/TwistStamped` | ROS → Gazebo. **Final velocity command** to the robot, published by Nav2's collision monitor |
| `/tb1/camera/image_raw` | `sensor_msgs/msg/Image` | Gazebo → ROS, **`waffle` only** |
| `/tb1/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | Gazebo → ROS, **`waffle` only** |

### Robot description and TF

| Topic | Type | Source |
|---|---|---|
| `/tb1/robot_description` | `std_msgs/msg/String` | `robot_state_publisher` |
| `/tb1/tf` | `tf2_msgs/msg/TFMessage` | Gazebo bridge (`odom → base_footprint`), `robot_state_publisher` (robot links), AMCL (`map → odom`) |
| `/tb1/tf_static` | `tf2_msgs/msg/TFMessage` | `robot_state_publisher` |

### Battery

| Topic | Type | Notes |
|---|---|---|
| `/tb1/battery_state` | `sensor_msgs/msg/BatteryState` | `mock_battery` at 1 Hz. Slowly drains from 100 % to 20 %, then resets |

### Localization

| Topic | Type | Notes |
|---|---|---|
| `/tb1/initialpose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | Input to AMCL (RViz "2D Pose Estimate", or CLI) |
| `/tb1/amcl_pose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | Robot pose in `map` |
| `/tb1/particle_cloud` | `nav2_msgs/msg/ParticleCloud` | AMCL particles |

The map itself is on the **global** `/map` topic (see the last table).

### Navigation: goals, plans and control

| Topic | Type | Notes |
|---|---|---|
| `/tb1/goal_pose` | `geometry_msgs/msg/PoseStamped` | Publish a pose here to start navigation (BT navigator) |
| `/tb1/plan` | `nav_msgs/msg/Path` | Global path from the planner server |
| `/tb1/plan_smoothed` | `nav_msgs/msg/Path` | Smoother server output |
| `/tb1/behavior_tree_log` | `nav2_msgs/msg/BehaviorTreeLog` | BT navigator state changes |
| `/tb1/local_plan` | `nav_msgs/msg/Path` | DWB controller local trajectory |
| `/tb1/received_global_plan` | `nav_msgs/msg/Path` | DWB debug |
| `/tb1/transformed_global_plan` | `nav_msgs/msg/Path` | DWB debug |
| `/tb1/marker` | `visualization_msgs/msg/MarkerArray` | DWB trajectory markers |
| `/tb1/evaluation` | `dwb_msgs/msg/LocalPlanEvaluation` | DWB critic scores (`debug_trajectory_details: true`) |
| `/tb1/cost_cloud` | `sensor_msgs/msg/PointCloud2` | DWB cost grid |
| `/tb1/speed_limit` | `nav2_msgs/msg/SpeedLimit` | Input to the controller server |

### Velocity pipeline

```
controller_server / behavior_server ─► /tb1/cmd_vel_nav ─► velocity_smoother ─► /tb1/cmd_vel_smoothed ─► collision_monitor ─► /tb1/cmd_vel ─► Gazebo
```

| Topic | Type | Notes |
|---|---|---|
| `/tb1/cmd_vel_nav` | `geometry_msgs/msg/TwistStamped` | Raw output of the controller and behaviors |
| `/tb1/cmd_vel_smoothed` | `geometry_msgs/msg/TwistStamped` | After the velocity smoother |
| `/tb1/cmd_vel_teleop` | `geometry_msgs/msg/TwistStamped` | Input for the `assisted_teleop` behavior |
| `/tb1/preempt_teleop` | `std_msgs/msg/Empty` | Stops `assisted_teleop` |
| `/tb1/collision_monitor_state` | `nav2_msgs/msg/CollisionMonitorState` | Collision-monitor action currently in effect |
| `/tb1/polygon_stop` | `geometry_msgs/msg/PolygonStamped` | Stop zone (visualization) |
| `/tb1/polygon_slowdown` | `geometry_msgs/msg/PolygonStamped` | Slow-down zone (visualization) |

### Costmaps

The same set of topics exists under `/tb1/local_costmap/` (a 3 × 3 m rolling window in `odom`) and under `/tb1/global_costmap/` (in `map`):

| Topic (relative to `.../local_costmap/` or `.../global_costmap/`) | Type |
|---|---|
| `costmap` | `nav_msgs/msg/OccupancyGrid` |
| `costmap_updates` | `map_msgs/msg/OccupancyGridUpdate` |
| `costmap_raw` | `nav2_msgs/msg/Costmap` |
| `published_footprint` | `geometry_msgs/msg/PolygonStamped` |
| `footprint` | `geometry_msgs/msg/Polygon` (input) |
| `voxel_grid` | `nav2_msgs/msg/VoxelGrid` (voxel layer) |

### Docking (opennav_docking: configured, but the world has no physical dock)

| Topic | Type |
|---|---|
| `/tb1/dock_pose` | `geometry_msgs/msg/PoseStamped` |
| `/tb1/filtered_dock_pose` | `geometry_msgs/msg/PoseStamped` |
| `/tb1/staging_pose` | `geometry_msgs/msg/PoseStamped` |

### RViz tool topics

| Topic | Type |
|---|---|
| `/tb1/clicked_point` | `geometry_msgs/msg/PointStamped` ("Publish Point" tool) |
| `/tb1/waypoints` | `visualization_msgs/msg/MarkerArray` (Nav2 panel waypoint mode) |

The RViz template also has displays for topics this setup never publishes, for example `downsampled_costmap`, `mobile_base/sensors/bumper_pointcloud`, `intel_realsense_r200_depth/*` and `*/voxel_marked_cloud`. These can appear in `ros2 topic list` with subscribers only.

### Lifecycle and bonds

| Topic | Type |
|---|---|
| `/tb1/<node>/transition_event` | `lifecycle_msgs/msg/TransitionEvent`. There is one per lifecycle node: `map_server`, `amcl`, `controller_server`, `local_costmap/local_costmap`, `global_costmap/global_costmap`, `smoother_server`, `planner_server`, `behavior_server`, `velocity_smoother`, `collision_monitor`, `bt_navigator`, `waypoint_follower`, `docking_server` |
| `/tb1/bond` | `bond/msg/Status` (lifecycle manager heartbeats) |

### Global topics shared by all robots

| Topic | Type | Notes |
|---|---|---|
| `/clock` | `rosgraph_msgs/msg/Clock` | Simulation time, from a single bridge for the whole world |
| `/map` | `nav_msgs/msg/OccupancyGrid` | Every robot's `map_server` publishes the same map here (`topic_name: /map`). Each robot's AMCL and global costmap subscribe to it |
| `/parameter_events`, `/rosout` | standard | ROS 2 infrastructure |

### Actions per robot

`ros2 topic list` does not show these; use `ros2 action list`.

| Action | Type |
|---|---|
| `/tb1/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` |
| `/tb1/navigate_through_poses` | `nav2_msgs/action/NavigateThroughPoses` |
| `/tb1/follow_waypoints` | `nav2_msgs/action/FollowWaypoints` |
| `/tb1/compute_path_to_pose` | `nav2_msgs/action/ComputePathToPose` |
| `/tb1/compute_path_through_poses` | `nav2_msgs/action/ComputePathThroughPoses` |
| `/tb1/follow_path` | `nav2_msgs/action/FollowPath` |
| `/tb1/smooth_path` | `nav2_msgs/action/SmoothPath` |
| `/tb1/spin`, `/tb1/backup`, `/tb1/drive_on_heading`, `/tb1/wait`, `/tb1/assisted_teleop` | `nav2_msgs/action/Spin`, `BackUp`, `DriveOnHeading`, `Wait`, `AssistedTeleop` |
| `/tb1/dock_robot`, `/tb1/undock_robot` | `nav2_msgs/action/DockRobot`, `UndockRobot` |
