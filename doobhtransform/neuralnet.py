"""
A module to approximate functions with neural networks.
"""

import torch
import torch.nn.functional as F


class MLP(torch.nn.Module):
    def __init__(
        self,
        input_dim,
        layer_widths,
        activate_final=False,
        activation_fn=torch.nn.LeakyReLU(),
    ):
        super(MLP, self).__init__()
        layers = []
        prev_width = input_dim
        for layer_width in layer_widths:
            layers.append(torch.nn.Linear(prev_width, layer_width))
            prev_width = layer_width
        self.input_dim = input_dim
        self.layer_widths = layer_widths
        self.layers = torch.nn.ModuleList(layers)
        self.activate_final = activate_final
        self.activation_fn = activation_fn

    def forward(self, x):
        for i, layer in enumerate(self.layers[:-1]):
            x = self.activation_fn(layer(x))
        x = self.layers[-1](x)
        if self.activate_final:
            x = self.activation_fn(x)
        return x


class V_Network(torch.nn.Module):

    def __init__(self, num_obs, dimension_state, dimension_obs, config):
        super().__init__()
        if config["full_obs"]:
            num_input_obs = [(num_obs - t) for t in range(num_obs)]
        else:
            num_input_obs = [1] * num_obs
        input_dimensions = [
            dimension_state + num * dimension_obs for num in num_input_obs
        ]
        layers = config["layers"]
        self.num_input_obs = num_input_obs
        self.standardization = config.get("standardization")
        self.net = torch.nn.ModuleList(
            [MLP(dim, layer_widths=layers + [1]) for dim in input_dimensions]
        )

    def forward(self, t, x, y):
        # t (int)
        # x.shape = (N, d)
        # y.shape=(N, T, p) in doobhtransform
        # y.shape=(T, p) in particlefilter

        # dimensions
        N = x.shape[0]
        p = y.shape[-1]
        q = self.num_input_obs[t]

        # index input observations
        idx = torch.arange(t, t + q)

        # handle shape of y argument
        if len(y.shape) == 2:
            y_ = y[idx, :].reshape((1, q * p)).repeat((N, 1))  # (N, q * p)
        if len(y.shape) == 3:
            y_ = y[:, idx, :].reshape((N, q * p))  # (N, q * p)

        # standardize inputs
        if self.standardization:
            x_c = (x - self.standardization["x_mean"]) / self.standardization["x_std"]
            y_c = (
                y_ - self.standardization["y_mean"].repeat(q)
            ) / self.standardization["y_std"].repeat(
                q
            )  # (N, q * p)
        else:
            x_c = x
            y_c = y_  # (N, q * p)

        # concat inputs
        h = torch.cat([x_c, y_c], -1)  # size (N, 1+d+p)

        # evaluate neural network
        out = torch.squeeze(self.net[t](h))  # size (N)

        return out


class Z_Network(torch.nn.Module):
    def __init__(self, num_obs, dimension_state, dimension_obs, config):
        super().__init__()
        if config["full_obs"]:
            num_input_obs = [(num_obs - t) for t in range(num_obs)]
        else:
            num_input_obs = [1] * num_obs
        input_dimensions = [
            dimension_state + num * dimension_obs + 1 for num in num_input_obs
        ]
        layers = config["layers"]
        self.num_input_obs = num_input_obs
        self.standardization = config.get("standardization")
        self.net = torch.nn.ModuleList(
            [
                MLP(dim, layer_widths=layers + [dimension_state])
                for dim in input_dimensions
            ]
        )

    def forward(self, t, s, x, y):
        # t (int)
        # s.shape = [1]
        # x.shape = (N, d)
        # y.shape=(N, T, p) in doobhtransform
        # y.shape=(T, p) in particlefilter

        # dimensions
        N = x.shape[0]
        p = y.shape[-1]
        q = self.num_input_obs[t]

        # index input observations
        idx = torch.arange(t, t + q)

        # handle shape of s
        if len(s.shape) == 0:
            s_ = s.repeat((N, 1))
        else:
            s_ = s

        # handle shape of y argument
        if len(y.shape) == 2:
            y_ = y[idx, :].reshape((1, q * p)).repeat((N, 1))  # (N, q * p)
        if len(y.shape) == 3:
            y_ = y[:, idx, :].reshape((N, q * p))  # (N, q * p)

        # standardize inputs
        if self.standardization:
            x_c = (x - self.standardization["x_mean"]) / self.standardization["x_std"]
            y_c = (
                y_ - self.standardization["y_mean"].repeat(q)
            ) / self.standardization["y_std"].repeat(
                q
            )  # (N, q * p)
        else:
            x_c = x
            y_c = y_  # (N, q * p)

        # concat inputs
        h = torch.cat([s_, x_c, y_c], -1)

        # evaluate neural network
        out = self.net[t](h)

        return out
