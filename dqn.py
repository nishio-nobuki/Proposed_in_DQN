# coding:utf-8
# [0]必要なライブラリのインポート
import gym  # 倒立振子(cartpole)の実行環境
import numpy as np
import time
from keras.models import Sequential
from keras.layers import Dense
from keras.optimizers import Adam
from keras.utils import plot_model
from collections import deque
from gym import wrappers  # gymの画像保存
from keras import backend as K
import tensorflow as tf
from tqdm import tqdm

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


# [1]損失関数の定義
# 損失関数にhuber関数を使用します 参考https://github.com/jaara/AI-blog/blob/master/CartPole-DQN.py
def huberloss(y_true, y_pred):
    err = y_true - y_pred
    cond = K.abs(err) < 1.0
    L2 = 0.5 * K.square(err)
    L1 = (K.abs(err) - 0.5)
    loss = tf.where(cond, L2, L1)  # Keras does not cover where function in tensorflow :-(
    return K.mean(loss)


# [2]Q関数をディープラーニングのネットワークをクラスとして定義
class QNetwork:
    def __init__(self, learning_rate=0.001, state_size=4, action_size=2, hidden_size=10):
        self.model = Sequential()
        self.model.add(Dense(hidden_size, activation='relu', input_dim=state_size))
        self.model.add(Dense(hidden_size, activation='relu'))
        self.model.add(Dense(action_size, activation='linear'))
        self.optimizer = Adam(lr=learning_rate)  # 誤差を減らす学習方法はAdamとし、勾配は最大1にクリップする
        # self.model.compile(loss='mse', optimizer=self.optimizer)
        self.model.compile(loss=huberloss, optimizer=self.optimizer)

    # 重みの学習
    def replay(self, memory, batch_size, gamma, targetQN):
        inputs = np.zeros((batch_size, 4))
        targets = np.zeros((batch_size, 2))
        mini_batch = memory.sample(batch_size)

        for i, (state_b, action_b, reward_b, next_state_b) in enumerate(mini_batch):
            inputs[i:i + 1] = state_b
            target = reward_b

            if not (next_state_b == np.zeros(state_b.shape)).all(axis=1):
                # 価値計算（DDQNにも対応できるように、行動決定のQネットワークと価値観数のQネットワークは分離）
                retmainQs = self.model.predict(next_state_b)[0]
                next_action = np.argmax(retmainQs)  # 最大の報酬を返す行動を選択する
                target = reward_b + gamma * targetQN.model.predict(next_state_b)[0][next_action]

            targets[i] = self.model.predict(state_b)  # Qネットワークの出力
            targets[i][action_b] = target  # 教師信号
        self.model.fit(inputs, targets, epochs=10, verbose=0)  # epochsは訓練データの反復回数、verbose=0は表示なしの設定


    # [※p1] 優先順位付き経験再生で重みの学習
    def prioritized_experience_replay(self, memory, batch_size, gamma, targetQN, memory_TDerror):

        # 0からTD誤差の絶対値和までの一様乱数を作成(昇順にしておく)
        sum_absolute_TDerror = memory_TDerror.get_sum_absolute_TDerror()
        generatedrand_list = np.random.uniform(0, sum_absolute_TDerror,batch_size)
        generatedrand_list = np.sort(generatedrand_list)

        # [※p2]作成した乱数で串刺しにして、バッチを作成する
        batch_memory = Memory(max_size=batch_size*10)
        idx_memory = Memory(max_size=batch_size*10)
        idx = 0
        tmp_sum_absolute_TDerror = 0
        for (i,randnum) in enumerate(generatedrand_list):

            while tmp_sum_absolute_TDerror < randnum:
                tmp_sum_absolute_TDerror += abs(memory_TDerror.buffer[idx]) + 0.0001
                idx += 1

            batch_memory.add(memory.buffer[idx])
            idx_memory.add(idx)


        # あとはこのバッチで学習する
        inputs = np.zeros((batch_memory.len(), 4))
        targets = np.zeros((batch_memory.len(), 2))
        for i, (state_b, action_b, reward_b, next_state_b) in enumerate(batch_memory.buffer):
            inputs[i:i + 1] = state_b
            target = reward_b

            if not (next_state_b == np.zeros(state_b.shape)).all(axis=1):
                # 価値計算（DDQNにも対応できるように、行動決定のQネットワークと価値観数のQネットワークは分離）
                retmainQs = self.model.predict(next_state_b)[0]
                next_action = np.argmax(retmainQs)  # 最大の報酬を返す行動を選択する
                target = reward_b + gamma * targetQN.model.predict(next_state_b)[0][next_action]

            targets[i] = self.model.predict(state_b)  # Qネットワークの出力
            targets[i][action_b] = target  # 教師信号

        #self.model.fit(inputs, targets, batch_size=batch_memory.len(), epochs=10, verbose=0)  # epochsは訓練データの反復回数、verbose=0は表示なしの設定
        self.model.fit(inputs, targets, epochs=10, verbose=0)

    def proposal_replay_method(self, memory, batch_size, gamma, targetQN, memory_TDerror):
        # 0からTD誤差の絶対値和までの一様乱数を作成(昇順にしておく)
        sum_absolute_TDerror = memory_TDerror.get_sum_absolute_TDerror()
        generatedrand_list = np.random.uniform(0, sum_absolute_TDerror, batch_size - multi_batch_memory.batch_memory[0].len())
        generatedrand_list = np.sort(generatedrand_list)

        # [※p2]作成した乱数で串刺しにして、バッチを作成する
        idx = 0
        tmp_sum_absolute_TDerror = 0
        for (i, randnum) in enumerate(generatedrand_list):

            while tmp_sum_absolute_TDerror < randnum:
                tmp_sum_absolute_TDerror += abs(memory_TDerror.buffer[idx]) + 0.0001
                idx += 1
            multi_batch_memory.batch_memory[0].add(memory.buffer[idx])
            multi_batch_memory.idx_memory[0].add(idx)

            id = idx
            #td_avr = memory_TDerror.get_avr_TDerror()
            #td_sd = memory_TDerror.get_standard_deviation(td_avr)
            # std_td = abs((memory_TDerror.buffer[id] - td_avr)/td_sd)
            #std_td = -(memory_TDerror.buffer[id] - td_avr) / td_sd

            if memory_TDerror.min() < 0 :
                for i in range(int(round(( - memory_TDerror.buffer[idx]) * max_ts_length / abs(memory_TDerror.min_under0())))):
                #for i in range(int(round(memory_TDerror.buffer[idx] * max_ts_length / memory_TDerror.max()))):
                #for i in range(int(round(abs(memory_TDerror.buffer[idx]) * max_ts_length / memory_TDerror.abs_max()))):
                    id -= 1
                    if id < 0:
                        break
                    multi_batch_memory.batch_memory[i+1].add(memory.buffer[id])
                    multi_batch_memory.idx_memory[i+1].add(id)



        # あとはこのバッチで学習する
        inputs = np.zeros((multi_batch_memory.batch_memory[0].len(), 4))
        targets = np.zeros((multi_batch_memory.batch_memory[0].len(), 2))
        for i, (state_b, action_b, reward_b, next_state_b) in enumerate(multi_batch_memory.batch_memory[0].buffer):
            inputs[i:i + 1] = state_b
            target = reward_b

            if not (next_state_b == np.zeros(state_b.shape)).all(axis=1):
                # 価値計算（DDQNにも対応できるように、行動決定のQネットワークと価値観数のQネットワークは分離）
                retmainQs = self.model.predict(next_state_b)[0]
                next_action = np.argmax(retmainQs)  # 最大の報酬を返す行動を選択する
                target = reward_b + gamma * targetQN.model.predict(next_state_b)[0][next_action]

            targets[i] = self.model.predict(state_b)  # Qネットワークの出力
            targets[i][action_b] = target  # 教師信号

        # self.model.fit(inputs, targets, batch_size=batch_memory.len(), epochs=10, verbose=0)  # epochsは訓練データの反復回数、verbose=0は表示なしの設定
        self.model.fit(inputs, targets, epochs=10, verbose=0)

        #shift memory
        multi_batch_memory.shift_memory()

# [2]Experience ReplayとFixed Target Q-Networkを実現するメモリクラス
class Memory:
    def __init__(self, max_size=1000):
        self.buffer = deque(maxlen=max_size)
        self.max_size = max_size

    def add(self, experience):
        self.buffer.append(experience)

    def sample(self, batch_size):
        idx = np.random.choice(np.arange(len(self.buffer)), size=batch_size, replace=False)
        return [self.buffer[ii] for ii in idx]

    def len(self):
        return len(self.buffer)

    def max(self):
        return max(self.buffer)

    def abs_max(self):
        return abs(max(self.buffer, key=abs))

    def min(self):
        return min(self.buffer)

    def min_under0(self):
        return min(min(self.buffer),0)

    def clear(self):
        self.buffer.clear()




# [※p3] Memoryクラスを継承した、TD誤差を格納するクラスです
class Memory_TDerror(Memory):
    def __init__(self, max_size=1000):
        super().__init__(max_size)

    # add, sample, len は継承されているので定義不要

    # TD誤差を取得
    def get_TDerror(self, memory, gamma, mainQN, targetQN):
        (state, action, reward, next_state) = memory.buffer[memory.len() - 1]   #最新の状態データを取り出す
        # 価値計算（DDQNにも対応できるように、行動決定のQネットワークと価値観数のQネットワークは分離）
        next_action = np.argmax(mainQN.model.predict(next_state)[0])  # 最大の報酬を返す行動を選択する
        target = reward + gamma * targetQN.model.predict(next_state)[0][next_action]
        TDerror = target - targetQN.model.predict(state)[0][action]
        return TDerror

    # TD誤差をすべて更新
    def update_TDerror(self, memory, gamma, mainQN, targetQN):
        for i in range(0, (self.len() - 1)):
            (state, action, reward, next_state) = memory.buffer[i]  # 最新の状態データを取り出す
            # 価値計算（DDQNにも対応できるように、行動決定のQネットワークと価値観数のQネットワークは分離）
            next_action = np.argmax(mainQN.model.predict(next_state)[0])  # 最大の報酬を返す行動を選択する
            target = reward + gamma * targetQN.model.predict(next_state)[0][next_action]
            TDerror = target - targetQN.model.predict(state)[0][action]
            self.buffer[i] = TDerror

    # TD誤差の絶対値和を取得
    def get_sum_absolute_TDerror(self):
        sum_absolute_TDerror = 0
        for i in range(0, (self.len() - 1)):
            sum_absolute_TDerror += abs(self.buffer[i]) + 0.0001  # 最新の状態データを取り出す

        return sum_absolute_TDerror

    def get_sum_TDerror(self):
        sum_TDerror = 0
        for i in range(0, (self.len() - 1)):
            sum_TDerror += np.sign(self.buffer[i])*(abs(self.buffer[i]) + 0.0001)

        return sum_TDerror

    def get_avr_TDerror(self):
        sum_TDerror = 0
        for i in range(0, (self.len() - 1)):
            sum_TDerror += np.sign(self.buffer[i])*(abs(self.buffer[i]) + 0.0001)

        return sum_TDerror/self.len()

    def get_standard_deviation(self, td_avr):
        sum = 0
        for i in range(0, (self.len() - 1)):
            sum += (np.sign(self.buffer[i])*(abs(self.buffer[i]) + 0.0001) - td_avr) ** 2
        return sum/self.len()

class MultiMemory:
    def __init__(self, memory_num, batch_size):
        self.memory_num = memory_num
        self.memory_size = batch_size
        self.batch_memory = []
        self.idx_memory = []
        for i in range(self.memory_num):
            self.batch_memory.append(Memory(max_size=batch_size))
            self.idx_memory.append(Memory(max_size=batch_size))

    def shift_memory(self):
        for i in range(self.memory_num-1):
            self.batch_memory[i] = self.batch_memory[i+1]
            self.idx_memory[i] = self.idx_memory[i + 1]
        self.batch_memory[self.memory_num - 1].clear()
        self.idx_memory[self.memory_num - 1].clear()

    def clear_all_memory(self):
        for i in range(self.memory_num):
            self.batch_memory[i].clear()
            self.idx_memory[i].clear()






# [3]カートの状態に応じて、行動を決定するクラス
class Actor:
    def get_action(self, state, episode, targetQN):  # [C]ｔ＋１での行動を返す
        # 徐々に最適行動のみをとる、ε-greedy法
        epsilon = 0.001 + 0.9 / (1.0 + episode)
        #epsilon = 0.1

        if epsilon <= np.random.uniform(0, 1):
            retTargetQs = targetQN.model.predict(state)[0]
            action = np.argmax(retTargetQs)  # 最大の報酬を返す行動を選択する

        else:
            action = np.random.choice([0, 1])  # ランダムに行動する

        return action


# [4] メイン関数開始----------------------------------------------------
# [4.1] 初期設定--------------------------------------------------------
DQN_MODE = 0  # 1がDQN、0がDDQNです
LENDER_MODE = 0  # 0は学習後も描画なし、1は学習終了後に描画する
Proposed = 1

env = gym.make('CartPole-v0')
num_episodes = 3999  # 総試行回数
max_number_of_steps = 200  # 1試行のstep数
goal_average_reward = 195  # この報酬を超えると学習終了
num_consecutive_iterations = 10  # 学習完了評価の平均計算を行う試行回数
total_reward_vec = np.zeros(num_consecutive_iterations)  # 各試行の報酬を格納
gamma = 0.99  # 割引係数
max_ts_length = 10
islearned = 0  # 学習が終わったフラグ
isrender = 0  # 描画フラグ
# ---
hidden_size = 16  # Q-networkの隠れ層のニューロンの数
learning_rate = 0.00001  # Q-networkの学習係数0.00001
memory_size = 1000  # バッファーメモリの大きさ
batch_size = 32  # Q-networkを更新するバッチの大きさ

learning_count = 0

ex_num = 10

result_learning_count = []
result_elapsed_time = []
result_episode = []





# [4.2]Qネットワークとメモリ、Actorの生成--------------------------------------------------------
#mainQN = QNetwork(hidden_size=hidden_size, learning_rate=learning_rate)  # メインのQネットワーク
#targetQN = QNetwork(hidden_size=hidden_size, learning_rate=learning_rate)  # 価値を計算するQネットワーク
#plot_model(mainQN.model, to_file='Qnetwork.png', show_shapes=True)        # Qネットワークの可視化
memory = Memory(max_size=memory_size)
memory_TDerror = Memory_TDerror(max_size=memory_size)
multi_batch_memory = MultiMemory(max_ts_length+1,batch_size)

actor = Actor()

# [4.3]メインルーチン--------------------------------------------------------
for experiment in tqdm(range(ex_num)):
    # 初期化
    mainQN = QNetwork(hidden_size=hidden_size, learning_rate=learning_rate)  # メインのQネットワーク
    targetQN = QNetwork(hidden_size=hidden_size, learning_rate=learning_rate)  # 価値を計算するQネットワーク
    #mainQN.model.reset_states()
    #targetQN.model.reset_states()
    memory.clear()
    memory_TDerror.clear()
    multi_batch_memory.clear_all_memory()
    islearned = 0
    learning_count = 0

    start = time.time()
    for episode in range(num_episodes):  # 試行数分繰り返す
        env.reset()  # cartPoleの環境初期化
        state, reward, done, _ = env.step(env.action_space.sample())  # 1step目は適当な行動をとる
        state = np.reshape(state, [1, 4])  # list型のstateを、1行4列の行列に変換
        episode_reward = 0

        for t in range(max_number_of_steps + 1):  # 1試行のループ
            if (islearned == 1) and LENDER_MODE:  # 学習終了したらcartPoleを描画する
                env.render()
                time.sleep(0.1)
                print(state[0, 0])  # カートのx位置を出力するならコメントはずす

            action = actor.get_action(state, episode, mainQN)  # 時刻tでの行動を決定する
            next_state, reward, done, info = env.step(action)  # 行動a_tの実行による、s_{t+1}, _R{t}を計算する
            next_state = np.reshape(next_state, [1, 4])  # list型のstateを、1行4列の行列に変換

            # 報酬を設定し、与える
            if done:
                next_state = np.zeros(state.shape)  # 次の状態s_{t+1}はない
                if t < 195:  #default 195
                    reward = -1  # 報酬クリッピング、報酬は1, 0, -1に固定
                else:
                    reward = 1  # 立ったまま195step超えて終了時は報酬
            else:
                reward = 0  # 各ステップで立ってたら報酬追加（はじめからrewardに1が入っているが、明示的に表す）

            episode_reward += 1  # reward  # 合計報酬を更新

            memory.add((state, action, reward, next_state))  # メモリの更新する


            # [※p4]TD誤差を格納する
            TDerror = memory_TDerror.get_TDerror(memory, gamma, mainQN, targetQN)
            memory_TDerror.add(TDerror)

            state = next_state  # 状態更新

            # [※p5]Qネットワークの重みを学習・更新する replay
            if (memory.len() > batch_size) and not islearned:
                if total_reward_vec.mean() < 0:
                    mainQN.replay(memory, batch_size, gamma, targetQN)
                else:
                    if Proposed == 1:
                        mainQN.proposal_replay_method(memory, batch_size, gamma, targetQN, memory_TDerror)
                    else:
                        mainQN.prioritized_experience_replay(memory, batch_size, gamma, targetQN, memory_TDerror)
                learning_count = learning_count + 1
            if DQN_MODE:
                targetQN = mainQN  # 行動決定と価値計算のQネットワークをおなじにする

            # 1施行終了時の処理
            if done:
                # [※p6]TD誤差のメモリを最新に計算しなおす
                targetQN = mainQN  # 行動決定と価値計算のQネットワークをおなじにする
                memory_TDerror.update_TDerror(memory, gamma, mainQN, targetQN)

                total_reward_vec = np.hstack((total_reward_vec[1:], episode_reward))  # 報酬を記録
                print('%d Episode finished after %f time steps / mean %f' % (episode, t + 1, total_reward_vec.mean()))
                break

        # 複数施行の平均報酬で終了を判断
        if total_reward_vec.mean() >= goal_average_reward:
            print('Episode %d train agent successfuly!' % episode)
            elapsed_time = time.time() - start
            print("elapsed_time:{0}".format(elapsed_time) + "[sec]")
            print("learning count:{0}".format(learning_count) + "[times]")
            #sns.distplot(memory_TDerror.buffer)
            #plt.show()
            islearned = 1
            result_episode.append(episode)
            result_learning_count.append(learning_count)
            result_elapsed_time.append(elapsed_time)
            if isrender == 0:  # 学習済みフラグを更新
                isrender = 1
                env = wrappers.Monitor(env, './movie/cartpole_prioritized',force=True)  # 動画保存する場合
            break

        if learning_count > 30000:
            print("leaning is failed")
            break



    if islearned == 0:
        elapsed_time = time.time() - start
        result_episode.append(300)
        result_learning_count.append(learning_count)
        result_elapsed_time.append(elapsed_time)




print("{0} experiment is done successfuly!".format(ex_num))
print(result_episode)
print(result_elapsed_time)
print(result_learning_count)

for i in range(ex_num):
    print('experiment %d' % i)
    print('episode: %d learning count: %d elapsed time: %f' % (result_episode[i], result_learning_count[i], result_elapsed_time[i]))

print('average of episode: %f' % (sum(result_episode)/len(result_episode)))
print('min of episode: %f' % (min(result_episode)))
print('average of learning count: %f' % (sum(result_learning_count)/len(result_learning_count)))
print('min of learning count: %f' % min(result_learning_count))
print('average of elapsed time: %f' % (sum(result_elapsed_time)/len(result_elapsed_time)))
print('min of elapsed time: %f' % (min(result_elapsed_time)))