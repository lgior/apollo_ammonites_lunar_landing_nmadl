"""
Minimum working example to train a Lunar Lander Agent using a DQN algorithm

Apollo Ammonites - NMA Deep Learning 2021
Team members:
    J. A. Moreno-Larios
    Haoqi Sun
    Giordano Ramos-Traslosheros

Requirements:
    xvfb - X-display for headless systems
    python-opengl - for movie rendering
    ffmpeg - for movie rendering
    stable-baseline3 - RNN framework
    box2d-py
    gym - Scenes
    pyvirtualdisplay
    matplotlib
    numpy
    - Note that there will be additional dependencies. pip, anaconda or 
        miniconda should be able to install them.
    - For miniconda, be sure to execure 
    'conda config --add channels conda-forge' to be able to 
    install software on an isolated environment
    - To have CUDA support, you'll need to run 
        conda install pytorch torchvision torchaudio cudatoolkit=10.2 -c pytorch
        https://pytorch.org/get-started/locally/

"""

# Imports
import io
import os
import glob
import sys
import torch
import base64
import numpy as np

from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import EvalCallback, StopTrainingOnMaxEpisodes, CallbackList, StopTrainingOnRewardThreshold
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor as sb3_Monitor

import gym
from gym.wrappers import Monitor
from gym.envs.registration import register
from apollo_lander import ImaginativeApolloLander
from model_based_dqn import ModelBasedDQN

# Plotting/Video functions
from IPython.display import HTML
from pyvirtualdisplay import Display
from IPython import display as ipythondisplay

display = Display(visible=0, size=(1400, 900))
display.start()

"""
Utility functions to enable video recording of gym environment
and displaying it.
To enable video, just do "env = wrap_env(env)""
"""

def show_video():
    mp4list = glob.glob('video/*.mp4')
    if len(mp4list) > 0:
        mp4 = mp4list[0]
        video = io.open(mp4, 'r+b').read()
        encoded = base64.b64encode(video)
        ipythondisplay.display(HTML(data='''<video alt="test" autoplay
            loop controls style="height: 400px;">
            <source src="data:video/mp4;base64,{0}" type="video/mp4" />
            </video>'''.format(encoded.decode('ascii'))))
    else:
        print("Could not find video")

def wrap_env(env, subdir):
    env = Monitor(env, './video/' + subdir, force = True)
    return env

"""
Basic DQN implementation
"""

nn_layers = [256, 256] #This is the configuration of your neural network. Currently, we have two layers, each consisting of 64 neurons.
                    #If you want three layers with 64 neurons each, set the value to [64,64,64] and so on.

learning_rate = 0.001 #This is the step-size with which the gradient descent is carried out.
                        #Tip: Use smaller step-sizes for larger networks.

buffer_size = int(sys.argv[1])
model_buffer_size = int(sys.argv[2])
batch_size = int(sys.argv[3])
train_freq = int(sys.argv[4])
gradient_steps = int(sys.argv[5])
        
log_dir = f"./tmp/gym-buffer_size{buffer_size}-model_buffer_size{model_buffer_size}-batch_size{batch_size}-train_freq{train_freq}-gradient_steps{gradient_steps}/"
os.makedirs(log_dir, exist_ok=True)


# Remove the environment if it was already registered
for env in gym.envs.registration.registry.env_specs.copy():
    if 'ImaginativeApolloLander-v0' in env:
        print("Remove {} from registry".format(env))
        del gym.envs.registration.registry.env_specs[env]
# Register our environment
register(
    id="ImaginativeApolloLander-v0",
    entry_point="apollo_lander:ImaginativeApolloLander", # Where our class is located
    #max_episode_steps=1000, # max_episode_steps / FPS = runtime seconds
    #reward_threshold=reward_threshold,
)
env = gym.make('LunarLander-v2')

#You can also load other environments like cartpole, MountainCar, Acrobot. Refer to https://gym.openai.com/docs/ for descriptions.
#For example, if you would like to load Cartpole, just replace the above statement with "env = gym.make('CartPole-v1')".

env_with_monitor = sb3_Monitor(env, log_dir )
#callback_on_best = StopTrainingOnRewardThreshold(reward_threshold=reward_threshold, verbose=1)
callback = CallbackList([
    EvalCallback(env_with_monitor,log_path = log_dir, deterministic=True), #For evaluating the performance of the agent periodically and logging the results.
    StopTrainingOnMaxEpisodes(1000)
    ])
policy_kwargs = dict(activation_fn=torch.nn.ReLU,
                             net_arch=nn_layers)
        
model = ModelBasedDQN(
        gym.make('ImaginativeApolloLander-v0'),   ##### this is the model
        # here is a special case, we assume model = the physics impelemented in ApolloLander
        # but in general, this model can be any mapping S,A-->R,S'
        
        "MlpPolicy", env_with_monitor, policy_kwargs = policy_kwargs,
        learning_rate=learning_rate,
        buffer_size=buffer_size, #size of experience of replay buffer. Set to 1 as batch update is not done
        model_buffer_size=model_buffer_size, # size of reply buffer saving data generated from model
        batch_size=batch_size,  #buffer_size + model_buffer_size
        learning_starts=1, #learning starts immediately!
        gamma=0.99, #discount facto. range is between 0 and 1.
        tau = 1,  #the soft update coefficient for updating the target network
        target_update_interval=1, #update the target network immediately.
        train_freq=(train_freq,"step"), #train the network at every step.
        max_grad_norm = 10, #the maximum value for the gradient clipping
        exploration_initial_eps = 1, #initial value of random action probability
        exploration_fraction = 0.5, #fraction of entire training period over which the exploration rate is reduced
        gradient_steps = gradient_steps, #number of gradient steps
        seed = 1, #seed for the pseudo random generators
        verbose = 1) #Set verbose to 1 to observe training logs. We encourage you to set the verbose to 1.

# You can also experiment with other RL algorithms like A2C, PPO, DDPG etc. Refer to  https://stable-baselines3.readthedocs.io/en/master/guide/examples.html
#for documentation. For example, if you would like to run DDPG, just replace "DQN" above with "DDPG".

"""
Now this is the part when our Apollo Anemmonite crashes because it has no arms to steer the lander
Lunar Lander before training
"""

"""
# test_env = wrap_env(gym.make("LunarLander-v2"))
test_env = wrap_env(gym.make('LunarLander-v2'), "before_training")
observation = test_env.reset()
total_reward = 0
while True:
    test_env.render()
    action, states = model.predict(observation, deterministic=False)
    observation, reward, done, info = test_env.step(action)
    total_reward += reward
    if done:
        break;
print(total_reward)
test_env.close()
#show_video() # You may need a notebook or an IDE like Spyder
# interactive shell like IPython to run this.
"""

"""
Here we train the model
"""

model.learn(total_timesteps=100000, log_interval=100, callback=callback)
# The performance of the training will be printed every 100 episodes. 
#Change it to 1, if you wish to view the performance at 
# every training episode.

"""
Now we render the lander behavior and display it on video
"""

"""
test_env = wrap_env(gym.make('LunarLander-v2'), "after_training")
observation = test_env.reset()
total_reward = 0
while True:
  test_env.render()
  action, _states = model.predict(observation, deterministic=True)
  observation, reward, done, info = test_env.step(action)
  total_reward += reward
  if done:
    break;
print(total_reward)
test_env.close()
#show_video()
"""

