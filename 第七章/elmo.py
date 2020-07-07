from allennlp.modules.elmo import Elmo, batch_to_ids
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class TextCNN(nn.Module):
    def __init__(self, opt):

        super(TextCNN, self).__init__()
        self.opt = opt
        self.use_gpu = self.opt.use_gpu

        if self.opt.emb_method == 'elmo':
            self.init_elmo()
        elif self.opt.emb_method == 'glove':
            self.init_glove()
        elif self.opt.emb_method == 'elmo_glove':
            self.init_elmo()
            self.init_glove()
            self.word_dim = self.opt.elmo_dim + self.opt.glove_dim

        self.cnns = nn.ModuleList([nn.Conv2d(1, self.opt.num_filters, (i, self.word_dim)) for i in self.opt.k])
        for cnn in self.cnns:
            nn.init.xavier_normal_(cnn.weight)
            nn.init.constant_(cnn.bias, 0.)
        self.linear = nn.Linear(self.opt.num_filters * len(self.opt.k), self.opt.num_labels)
        nn.init.xavier_uniform_(self.linear.weight)
        nn.init.constant_(self.linear.bias, 0)
        self.dropout = nn.Dropout(self.opt.dropout)

    def init_elmo(self):
        '''
        initilize the ELMo model
        '''
        self.elmo = Elmo(self.opt.elmo_options_file, self.opt.elmo_weight_file, 1)
        self.word_dim = self.opt.elmo_dim


    def get_elmo(self, sentence_lists):
        '''
        get the ELMo word embedding vectors for a sentences
        '''
        character_ids = batch_to_ids(sentence_lists)
        if self.opt.use_gpu:
            character_ids = character_ids.to(self.opt.device)
        embeddings = self.elmo(character_ids)
        return embeddings['elmo_representations'][0]

    def forward(self, x):
        if self.opt.emb_method == 'elmo':
            word_embs = self.get_elmo(x)
        elif self.opt.emb_method == 'glove':
            word_embs = self.get_glove(x)
        elif self.opt.emb_method == 'elmo_glove':
            glove = self.get_glove(x)
            elmo = self.get_elmo(x)
            word_embs = torch.cat([elmo, glove], -1)

        x = word_embs.unsqueeze(1)
        x = [F.relu(cnn(x)).squeeze(3) for cnn in self.cnns]   
        x = [F.max_pool1d(i, i.size(2)).squeeze(2) for i in x]
        x = torch.cat(x, 1)
        x = self.dropout(x)
        x = self.linear(x)   
        return x
