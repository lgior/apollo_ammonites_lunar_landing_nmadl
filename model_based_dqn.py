#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 10 12:49:49 2021 EST

@author: haoqisun
"""
import numpy as np
import torch as th
from torch.nn import functional as F
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import ConvertCallback
from gym.envs.box2d.lunar_lander import *


class ModelBasedDQN(DQN):
    """
    We modify DQN class to make it model based
    where is the model is a physical model,
    taken from gym.envs.box2d.lunar_lander.LunarLander.step()
    https://github.com/openai/gym/blob/master/gym/envs/box2d/lunar_lander.py#L266
    """
    def __init__(
        self,
        model,  ########### specific to ModelBasedDQN
        policy,
        env,
        learning_rate= 1e-4,
        buffer_size= 1000000,  # 1e6
        model_buffer_size= 1000000,  # 1e6  ########### specific to ModelBasedDQN
        learning_starts= 50000,
        batch_size= 32,
        tau= 1.0,
        gamma= 0.99,
        train_freq= 4,
        gradient_steps= 1,
        replay_buffer_class= None,
        replay_buffer_kwargs= None,
        optimize_memory_usage= False,
        target_update_interval= 10000,
        exploration_fraction= 0.1,
        exploration_initial_eps= 1.0,
        exploration_final_eps= 0.05,
        max_grad_norm= 10,
        tensorboard_log= None,
        create_eval_env= False,
        policy_kwargs= None,
        verbose= 0,
        seed= None,
        device= "auto",
        _init_setup_model= True):
        self.model = model
        self.model_buffer_size = model_buffer_size
        super().__init__(
            policy,
            env,
            learning_rate,
            buffer_size,
            learning_starts,
            batch_size,
            tau,
            gamma,
            train_freq,
            gradient_steps,
            replay_buffer_class,
            replay_buffer_kwargs,
            optimize_memory_usage,
            target_update_interval,
            exploration_fraction,
            exploration_initial_eps,
            exploration_final_eps,
            max_grad_norm,
            tensorboard_log,
            create_eval_env,
            policy_kwargs,
            verbose,
            seed,
            device,
            _init_setup_model,
        )
    
    def _setup_model(self):
        super()._setup_model()
        self.replay_buffer_model = self.replay_buffer_class(
                self.model_buffer_size,
                self.observation_space,
                self.action_space,
                self.device,
                optimize_memory_usage=self.optimize_memory_usage,
                **self.replay_buffer_kwargs,
            )
            
    def _generate_from_model(self, Nsample=1, random_seed=None):
        """
        based on https://github.com/DLR-RM/stable-baselines3/blob/v1.1.0/stable_baselines3/common/off_policy_algorithm.py#L510
        
        Randomly sample a state *from experienced states*
        Randomly sample an action
        run the model one step
        save (state, action, new state, reward) to buffer
        repeat above `Nsample` times
        """
        np.random.seed(random_seed)
        for _ in range(Nsample):
            """
            # randomly sample a state using the final state after running the model `Kinit` steps with random actions
            self.model.reset()
            Kinit = np.random.randint(1,100)
            for i in range(Kinit):
                action = self.model.action_space.sample()
                state, reward, done, infos = self.model.step([action])
            # now the model is at a random state
            """
            # randomly sample a state *from experienced states*
            if self.replay_buffer.full:
                experienced_states = self.replay_buffer.observations
            else:
                experienced_states = self.replay_buffer.observations[:self.replay_buffer.pos]
            idx = np.random.choice(range(len(experienced_states)), 1)[0]
            state = experienced_states[idx][0].astype(float)
            self.model.reset(*state)
            
            # randomly sample an action
            action = self.model.action_space.sample()
            
            # run model one step
            last_state = state
            state, reward, done, infos = self.model.step(action)
            
            #TODO add noise to state

            # Store data in replay buffer
            self.replay_buffer_model.add([last_state], [state], [action], [reward], [done], [infos])
                
    def train(self, gradient_steps: int, batch_size: int = 100) -> None:
        # Update learning rate according to schedule
        self._update_learning_rate(self.policy.optimizer)

        # add data generated from model
        if self.model_buffer_size>0:
            #TODO Not implemented: self.learn_model_from_memory()
            self._generate_from_model(self.model_buffer_size, 2021)
            rbs = [self.replay_buffer, self.replay_buffer_model]
        else:
            rbs = [self.replay_buffer]
        
        losses = []
        for _ in range(gradient_steps):
            for rb in rbs:
                # Sample replay buffer
                replay_data = rb.sample(batch_size, env=self._vec_normalize_env)

                with th.no_grad():
                    # Compute the next Q-values using the target network
                    next_q_values = self.q_net_target(replay_data.next_observations)
                    # Follow greedy policy: use the one with the highest value
                    next_q_values, _ = next_q_values.max(dim=1)
                    # Avoid potential broadcast issue
                    next_q_values = next_q_values.reshape(-1, 1)
                    # 1-step TD target
                    target_q_values = replay_data.rewards + (1 - replay_data.dones) * self.gamma * next_q_values

                # Get current Q-values estimates
                current_q_values = self.q_net(replay_data.observations)

                # Retrieve the q-values for the actions from the replay buffer
                current_q_values = th.gather(current_q_values, dim=1, index=replay_data.actions.long())

                # Compute Huber loss (less sensitive to outliers)
                loss = F.smooth_l1_loss(current_q_values, target_q_values)
                losses.append(loss.item())

                # Optimize the policy
                self.policy.optimizer.zero_grad()
                loss.backward()
                # Clip gradient norm
                th.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                self.policy.optimizer.step()

        # Increase update counter
        self._n_updates += gradient_steps

        self.logger.record("train/n_updates", self._n_updates, exclude="tensorboard")
        self.logger.record("train/loss", np.mean(losses))
