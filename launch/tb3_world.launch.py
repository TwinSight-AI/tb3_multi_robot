#!/usr/bin/env python3
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Authors: Arshad Mehmood

import os
import yaml

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    IncludeLaunchDescription,
    DeclareLaunchArgument,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from multi_robot_scripts.utils import load_sdf_with_namespace, create_namespaced_bridge_yaml

def generate_launch_description():
    # Paths
    tb3_multi_dir = get_package_share_directory('tb3_multi_robot')
    ros_gz_sim_dir = get_package_share_directory('ros_gz_sim')

    # Simulation config
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    world_path = os.path.join(tb3_multi_dir, 'worlds', 'tb3_world.world')

    # Launch Gazebo server and client
    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(ros_gz_sim_dir, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': f'-r -s -v2 {world_path}', 'on_exit_shutdown': 'true'}.items()
    )
    gzclient_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(ros_gz_sim_dir, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': '-g -v2', 'on_exit_shutdown': 'true'}.items()
    )

    # Optional TwinSight robot_adapter (one adapter_node per robot).
    # Off by default so the simulation runs standalone; enabling it requires
    # the robot_adapter package to be built in the same workspace.
    use_robot_adapter = LaunchConfiguration('use_robot_adapter')
    declare_use_robot_adapter = DeclareLaunchArgument(
        'use_robot_adapter',
        default_value='false',
        description='Start a TwinSight robot_adapter node for every robot '
                    '(requires the robot_adapter package).'
    )

    # Main LaunchDescription
    ld = LaunchDescription()
    ld.add_action(declare_use_robot_adapter)
    ld.add_action(gzserver_cmd)
    ld.add_action(gzclient_cmd)

    # Load robot config
    robot_config_path = os.path.join(tb3_multi_dir, 'config', 'robots.yaml')
    with open(robot_config_path, 'r') as f:
        config = yaml.safe_load(f)

    robots = [r for r in config['robots'] if r.get('enabled', True)]
    # Shared across all robots' adapters (one TwinSight backend per deployment).
    api_base_url = os.environ.get('TWINSIGHT_API_BASE_URL', 'http://localhost:8001')
    tb3_model = os.environ.get('TURTLEBOT3_MODEL', 'burger')
    model_dir = f'turtlebot3_{tb3_model}'
    # Remap RSP's /tf → tf so it publishes to /<namespace>/tf (not global /tf).
    # Nav2 with use_namespace gives each robot its own TF tree on /<ns>/tf.
    remappings = [("/tf", "tf"), ("/tf_static", "tf_static")]
    urdf_file_name = 'turtlebot3_' + tb3_model + '.urdf'
    urdf_path = os.path.join(
        tb3_multi_dir,
        'urdf',
        urdf_file_name)

    with open(urdf_path, 'r') as infp:
        robot_desc = infp.read()

    for robot in robots:
        namespace = robot['name']

        sdf_path = os.path.join(tb3_multi_dir, 'models', model_dir, 'model.sdf')
        patched_sdf = load_sdf_with_namespace(sdf_path, namespace)

        robot_state_publisher = Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            namespace=namespace,
            remappings=remappings,
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'robot_description': robot_desc,
                'frame_prefix': ''
            }])

        spawner_node = Node(
            package='ros_gz_sim',
            executable='create',
            namespace=namespace,
            arguments=[
                '-name', f'{namespace}_{tb3_model}',
                '-string', patched_sdf,
                '-x', str(robot['x_pose']),
                '-y', str(robot['y_pose']),
                '-z', '0.01',
            ],
            output='screen',
        )

        bridge_template = os.path.join(tb3_multi_dir, 'params', f'{tb3_model}_bridge.yaml')
        namespaced_bridge = create_namespaced_bridge_yaml(bridge_template, namespace)

        bridge_node = Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name=f'{namespace}_bridge',
            arguments=['--ros-args', '-p', f'config_file:={namespaced_bridge}'],
            output='screen',
        )

        # Add image bridge if model has camera
        image_bridge = None
        if tb3_model != 'burger':
            image_bridge = Node(
                package='ros_gz_image',
                executable='image_bridge',
                namespace=namespace,
                arguments=['/' + namespace + '/camera/image_raw'],
                output='screen',
            )

        # TwinSight platform robot_id/robot_secret are per-robot credentials,
        # so they're sourced from <ROBOT_NAME>_ROBOT_ID / _ROBOT_SECRET env
        # vars (see docker-compose.yaml) rather than robots.yaml. Falls back
        # to the adapter's built-in dummy UUID when unset.
        env_prefix = namespace.upper()
        robot_id = os.environ.get(f'{env_prefix}_ROBOT_ID', '')
        robot_secret = os.environ.get(f'{env_prefix}_ROBOT_SECRET', '')


        # Only executed when use_robot_adapter:=true, so the robot_adapter
        # package is not needed for a standalone run.
        robot_adapter_node = Node(
            package='robot_adapter',
            executable='adapter_node',
            namespace=namespace,
            output='screen',
            condition=IfCondition(use_robot_adapter),
            parameters=[{
                'api_base_url': api_base_url,
                'robot_id': robot_id,
                'robot_secret': robot_secret,
                'use_dummy_uuid': False,
                # Relative (no leading slash) so they resolve under this
                # node's namespace instead of the adapter's absolute
                # defaults (/odom, /battery_state, /imu), which every
                # robot's adapter would otherwise subscribe to identically.
                'odom_topic': 'odom',
                'battery_topic': 'battery_state',
                'imu_topic': 'imu',
            }]
        )

        # Add robot-related nodes
        ld.add_action(robot_state_publisher)
        ld.add_action(spawner_node)
        ld.add_action(bridge_node)
        ld.add_action(robot_adapter_node)

        if image_bridge:
            ld.add_action(image_bridge)

    # In a multi-robot setup using Gazebo Sim (Harmonic or later), each robot typically
    # requires a separate ROS-Gazebo bridge to relay topics such as sensor data, odometry,
    # and control commands between Gazebo and ROS 2.
    # However, some topics like `/clock` are *global* and should be published only once
    # to avoid conflicts or duplication. If multiple bridges publish `/clock`, it may lead
    # to inconsistent simulation time behavior across nodes or unnecessary topic traffic.
    # Therefore, the `/clock` topic is handled separately:
    # - It is excluded from the per-robot bridge configuration files (YAMLs).
    # - A dedicated, single bridge instance is launched to publish `/clock` from Gazebo to ROS 2.
    # This ensures consistent simulation time across the entire ROS 2 system while supporting
    # multiple robot instances with their own bridges.

    # Global clock bridge
    clock_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='clock_bridge',
        output='screen',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        )
    ld.add_action(clock_bridge)

    # Add GZ model path to env
    ld.add_action(AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.join(tb3_multi_dir, 'models'))
    )

    return ld
