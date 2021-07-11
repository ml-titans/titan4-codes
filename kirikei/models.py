import tensorflow as tf
from tensorflow.keras import layers, initializers
from tensorflow.keras.models import Sequential
from tensorflow.keras.optimizers import SGD, Adam

import tensorflow_addons as tfa

physical_devices = tf.config.list_physical_devices('GPU')
tf.config.set_visible_devices(physical_devices[0], 'GPU')
tf.config.experimental.set_memory_growth(physical_devices[0], True)

class MLPBlock(layers.Layer):
    def __init__(self, hidden_dim, input_dim, activation='gelu', dropout_rate=0, batch_norm=False, dense_params={}, **kwargs):
        super().__init__(name='mlp_block', **kwargs)
        self.dense1 = layers.Dense(hidden_dim, **dense_params)
        
        if dropout_rate > 0:
            self.dropout = layers.Dropout(dropout_rate)
        
        if batch_norm:
            self.batchnorm = layers.BatchNormalization()
        
        if activation == 'gelu':
            self.act = tfa.activations.gelu
        else:
            self.act = layers.Activation(activation)
            
        self.dense2 = layers.Dense(input_dim, **dense_params)
        
    def call(self, x):
        x = self.dense1(x)
        x = self.act(x)
        
        if hasattr(self, 'dropout'):
            x = self.dropout(x)
        
        if hasattr(self, 'batchnorm'):
             x = self.batchnorm(x)
        
        x = self.dense2(x)
        return x
    
    def get_config(self):
        return super().get_config()
        
class MixerBlock(layers.Layer):
    def __init__(self, tokens_mlp_dim, channels_mlp_dim, token_input_dim, channel_input_dim, mlp_block_params={}, **kwargs):
        
        self.layer_norm1 = layers.LayerNormalization()
        self.permute1 = layers.Permute((2, 1))
        self.token_mix = MLPBlock(tokens_mlp_dim, token_input_dim, **mlp_block_params)
        self.permute2 = layers.Permute((2, 1))
        self.layer_norm2 = layers.LayerNormalization()
        self.channel_mix = MLPBlock(channels_mlp_dim, channel_input_dim, **mlp_block_params)
        super().__init__(**kwargs)
        
    def call(self, x):
        y = self.layer_norm1(x)
        # transpose to channel x input
        y = self.permute1(y)

        # token mixing
        # When dense feed data with the shape (batch_size, a, b), dense reshape into (batch_size x a, b)
        # Therefore, each a is feeded with nn as a different sample
        # Here, a means each patch
        token_mixing = self.token_mix(y)
        
        # transpose to input x channel
        token_mixing = self.permute2(token_mixing)
        
        # skip connect 
        x = x + token_mixing

        y = self.layer_norm2(x)
        
        # channel mixins
        channel_mixing = self.channel_mix(y)
        
        # skip connect
        output = x + channel_mixing
        return output
    
    def get_config(self):
        # https://qiita.com/taiga518/items/b2154b661e7baf56031e
        return super().get_config()
    
def mlp_mixer(input_shape, num_classes=10, num_blocks=4, patch_size=4, 
              hidden_dim=128, tokens_mlp_dim=64, channels_mlp_dim=128, conv1d=False, aug=[], mlp_block_params={}):
    
    
    channels = hidden_dim
    rows = input_shape[0] // patch_size
    cols = input_shape[1] // patch_size # for 2d
    
    model = Sequential(aug)
    
    if conv1d:
        print('set conv1d model')
        cols = 1
        model.add(layers.Conv1D(hidden_dim, kernel_size=patch_size,
                      strides=patch_size, padding="valid", input_shape=input_shape)) # no padding
    
    else:        
        model.add(layers.Conv2D(hidden_dim, kernel_size=patch_size,
                      strides=patch_size, padding="valid", input_shape=input_shape)) # no padding
    
    # input -> batch_size x rows x cols x channels (hidden_dim)
    model.add(layers.Reshape((rows*cols, channels)))
    
    for _ in range(num_blocks):
        model.add(MixerBlock(tokens_mlp_dim, channels_mlp_dim, mlp_block_params=mlp_block_params, 
                             token_input_dim=rows*cols, channel_input_dim=channels))
        
    model.add(layers.LayerNormalization())
    model.add(layers.GlobalAveragePooling1D())
    model.add(layers.Dense(num_classes, activation='softmax', kernel_initializer=initializers.Zeros()))
    
    return model

def augmentation_layers():
    return [
        layers.experimental.preprocessing.Normalization(),
        layers.experimental.preprocessing.RandomFlip("horizontal"),
        layers.experimental.preprocessing.RandomRotation(factor=0.02),
    ]


class GELU(layers.Layer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gelu = tfa.activations.gelu
        
    def call(self, x):
        return self.gelu(x)
        

def simple_mlp(input_shape, layers_list, activation='relu', dropout_rate=0, num_classes=10, aug=True):
    """
    Args:
        input_shape(tuple): input data shape
        layers(List(int)): layer config
    
    """
    if aug:
        model = Sequential(augmentation_layers())
    else:
        model = Sequential()
        
    model.add(layers.Flatten(input_shape=input_shape))
    for i, node in enumerate(layers_list):
        model.add(layers.Dense(node))
            
        if activation == 'gelu':
            model.add(GELU())
        else:
            model.add(layers.Activation(activation))
            
        if dropout_rate > 0:
            model.add(layers.Dropout(dropout_rate))
            
    model.add(layers.Dense(num_classes, activation='softmax'))
    return model
        


def cnn_mlp(input_shape, layers_list, activation='relu', num_classes=10, dropout_rate=0, conv_params={}, conv1d=False, aug=True):
    """
    Args:
        input_shape(tuple): input data shape
        layers(List(int)): layer config
    
    """
    
    if aug:
        model = Sequential(augmentation_layers())
    else:
        model = Sequential()
        
    if conv1d:
        model.add(layers.Conv1D(conv_params['filters'], conv_params['kernel_size'], input_shape=input_shape))
    else:
        model.add(layers.Conv2D(conv_params['filters'], conv_params['kernel_size'], input_shape=input_shape))
    
    model.add(layers.Flatten())
    
    for i, node in enumerate(layers_list):
        model.add(layers.Dense(node))
            
        if activation == 'gelu':
            model.add(GELU())
        else:
            model.add(layers.Activation(activation))
            
        if dropout_rate > 0:
            model.add(layers.Dropout(dropout_rate))
            
    model.add(layers.Dense(num_classes, activation='softmax'))
    return model


def cnn(input_shape, layers_list, activation='relu', num_classes=10, dropout_rate=0, conv1d=False, aug=True):
    """
    Args:
        input_shape(tuple): input data shape
        layers(List(int)): layer config
    
    """
    
    if aug:
        model = Sequential(augmentation_layers())
    else:
        model = Sequential()
    
    for i, l in enumerate(layers_list):
        
        if conv1d:
            if i < 1:
                model.add(layers.Conv1D(input_shape=input_shape, **l))
            else:
                model.add(layers.Conv1D(**l))
        else:
            if i < 1:
                model.add(layers.Conv2D(input_shape=input_shape, **l))
            else:
                model.add(layers.Conv2D(**l))
            
        if activation == 'gelu':
            model.add(GELU())
        else:
            model.add(layers.Activation(activation))
            
        if dropout_rate > 0:
            model.add(layers.Dropout(dropout_rate))
    
    model.add(layers.Flatten())
    model.add(layers.Dense(num_classes, activation='softmax'))
    return model


def lstm(input_shape, layers_list, activation='relu', num_classes=10, dropout_rate=0, lstm_params={}, aug=True):
    """
    Args:
        input_shape(tuple): input data shape
        layers(List(int)): layer config
    
    """
    
    if aug:
        model = Sequential(augmentation_layers())
    else:
        model = Sequential()
    
    for i, node in enumerate(layers_list):
        if i < 1:
            model.add(layers.LSTM(node, input_shape=input_shape, return_sequences=True, **lstm_params))
        else:
            model.add(layers.LSTM(node, **lstm_params))
            
        if activation == 'gelu':
            model.add(GELU())
        else:
            model.add(layers.Activation(activation))
            
        if dropout_rate > 0:
            model.add(layers.Dropout(dropout_rate))
            
    model.add(layers.Dense(num_classes, activation='softmax'))
    return model