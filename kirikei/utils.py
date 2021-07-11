import itertools, os, json
import pandas as pd

import models

import tensorflow as tf
from tensorflow.keras.regularizers import l2, l1
from tensorflow.keras.optimizers import SGD, Adam

def mixer_parameter_search(x_train, y_train, x_test, y_test, train_params={}, path='./results/', start_i=0):
    
    num_blocks = [24, 48]
    patch_size = [2, 8, 16]
    hidden_dim=[16, 64, 256]
    tokens_mlp_dim= [16, 64, 256] 
    channels_mlp_dim=[16, 64, 256]
    activation= ['gelu','relu']
    dropout_rate=[0, 0.5]
    batch_norm=[True, False]
    kernel_initializer=['he_normal']
    
    epochs = train_params['epochs']
    batch_size = train_params['batch_size']
    learning_rate = train_params['learning_rate']
    
    print(train_params)
    
    base_folder = os.path.join(path)
        
    if not os.path.exists(base_folder):
        os.makedirs(base_folder)
        
    save_results(train_params, os.path.join(base_folder, 'train_params.json'), 'json')
    
    i = start_i
    
    for (n, p, h, tm, cm, a, dr, bn, ki) in itertools.product(
        num_blocks, patch_size, hidden_dim, tokens_mlp_dim, channels_mlp_dim, activation, dropout_rate, batch_norm,
        kernel_initializer
    ):
        
        parameters = dict(
            num_blocks = n,
            patch_size=p, 
            hidden_dim=h, 
            tokens_mlp_dim=tm, 
            channels_mlp_dim=cm,
            mlp_block_params=dict(
                activation=a,
                dropout_rate=dr,
                batch_norm=bn,
                dense_params=dict(
                    kernel_initializer=ki,
                )
            )
        )
        
        if i < 826:
            i+=1
            continue
        
        print(i, parameters)
        
        save_folder = os.path.join(path, str(i))
        
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
            
        
        mixer_model = models.mlp_mixer((32, 32, 3), num_classes=10, aug=models.augmentation_layers(),
                                       **parameters)
        mixer_model.compile(
            Adam(learning_rate=learning_rate), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
        
        
        # 最も良いものを保存
        callbacks = []
        weight_path = os.path.join(save_folder, 'model_weights.ckpt')
        callbacks.append(tf.keras.callbacks.ModelCheckpoint(
            weight_path, monitor='val_loss', verbose=0, save_best_only=True,
            save_weights_only=True
        ))

        history = mixer_model.fit(x_train, y_train, validation_split=0.2, epochs=epochs, batch_size=batch_size, verbose=False,
                                 callbacks=callbacks)
        
        # 再ロード
        mixer_model.load_weights(weight_path)
        
        (loss, acc) = mixer_model.evaluate(x_test, y_test)
        
        # parameters = convert_reg_params(parameters)        
        save_results(parameters, os.path.join(save_folder, 'params.json'), 'json')
        save_results(history.history, os.path.join(save_folder, 'history.json'), 'json')
        save_results(dict(test_loss=loss, test_acc=acc), os.path.join(save_folder, 'evaluate.json'), 'json')
        
        i+=1
        
    return None
    
def convert_reg_params(parameters):
    
    kernel_params = parameters['mlp_block_params']['dense_params']['kernel_regularizer']
    
    if kernel_params is not None:
        parameters['mlp_block_params']['dense_params']['kernel_regularizer'] = kernel_params.get_config()
    return parameters
    
def save_results(data, path, file_type='pkl'):
    """学習結果を格納するための関数
    """
    if file_type == 'pkl':
        pd.to_pickle(data, path)
    elif file_type == 'json':
        with open(path, mode='w') as f:
            json.dump(data, f)
    elif file_type == 'csv':
        pd.to_csv(data, path)
    else:
        raise ValueError('Unknown Data Type')
    
  